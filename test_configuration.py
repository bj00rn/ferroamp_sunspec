import argparse

import pytest

from ferroamp_sunspec.configuration import parse_configuration


@pytest.fixture
def configured_parser(monkeypatch):
    for key in ("MQTT_HOST", "MQTT_PORT", "TRACE_MODBUS", "LOG_LEVEL"):
        monkeypatch.delenv(key, raising=False)
        monkeypatch.delenv(f"{key}_FILE", raising=False)
    monkeypatch.setattr("sys.argv", ["bridge"])
    parser = argparse.ArgumentParser()
    parser.add_argument("--mqtt-host", required=True)
    parser.add_argument("--mqtt-port", type=int, default=1883)
    parser.add_argument("--trace-modbus", action="store_true")
    parser.add_argument("--log-level", type=str.upper, choices=("INFO", "DEBUG"), default="INFO")
    return parser


def test_environment_and_cli_precedence(configured_parser, monkeypatch):
    monkeypatch.setenv("MQTT_HOST", "environment-host")
    monkeypatch.setenv("MQTT_PORT", "invalid-but-overridden")
    monkeypatch.setenv("TRACE_MODBUS", "yes")
    monkeypatch.setenv("LOG_LEVEL", "debug")
    monkeypatch.setattr("sys.argv", ["bridge", "--mqtt-port=1885"])
    args = parse_configuration(configured_parser)
    assert args.mqtt_host == "environment-host"
    assert args.mqtt_port == 1885
    assert args.trace_modbus is True
    assert args.log_level == "DEBUG"


def test_defaults_and_false_boolean(configured_parser, monkeypatch):
    monkeypatch.setenv("MQTT_HOST", "host")
    monkeypatch.setenv("TRACE_MODBUS", "false")
    args = parse_configuration(configured_parser)
    assert args.mqtt_port == 1883
    assert args.trace_modbus is False


@pytest.mark.parametrize("key,value", [
    ("MQTT_PORT", "not-a-number"),
    ("TRACE_MODBUS", "maybe"),
    ("LOG_LEVEL", "verbose"),
])
def test_invalid_environment_reports_error(configured_parser, monkeypatch, capsys, key, value):
    monkeypatch.setenv("MQTT_HOST", "host")
    monkeypatch.setenv(key, value)
    with pytest.raises(SystemExit) as exc:
        parse_configuration(configured_parser)
    assert exc.value.code == 2
    assert key in capsys.readouterr().err


def test_missing_host_is_still_required(configured_parser):
    with pytest.raises(SystemExit):
        parse_configuration(configured_parser)


def test_cli_overrides_environment(configured_parser, monkeypatch):
    monkeypatch.setenv("MQTT_HOST", "environment-host")
    monkeypatch.setenv("TRACE_MODBUS", "false")
    monkeypatch.setattr("sys.argv", ["bridge", "--mqtt-host", "cli-host", "--trace-modbus"])
    args = parse_configuration(configured_parser)
    assert args.mqtt_host == "cli-host"
    assert args.trace_modbus is True


def test_file_configuration_for_all_arguments(configured_parser, monkeypatch, tmp_path):
    for key, value in {
        "MQTT_HOST": "file-host",
        "MQTT_PORT": "1885",
        "TRACE_MODBUS": "yes",
        "LOG_LEVEL": "debug",
    }.items():
        path = tmp_path / key
        path.write_text(value + "\r\n", encoding="utf-8")
        monkeypatch.setenv(f"{key}_FILE", str(path))
    args = parse_configuration(configured_parser)
    assert args.mqtt_host == "file-host"
    assert args.mqtt_port == 1885
    assert args.trace_modbus is True
    assert args.log_level == "DEBUG"


def test_cli_and_environment_override_unreadable_files(configured_parser, monkeypatch):
    monkeypatch.setenv("MQTT_HOST", "environment-host")
    monkeypatch.setenv("MQTT_HOST_FILE", "/nonexistent/mqtt-host")
    monkeypatch.setenv("MQTT_PORT_FILE", "/nonexistent/mqtt-port")
    monkeypatch.setattr("sys.argv", ["bridge", "--mqtt-port=1885"])
    args = parse_configuration(configured_parser)
    assert args.mqtt_host == "environment-host"
    assert args.mqtt_port == 1885


@pytest.mark.parametrize("contents", [None, b"\xff", b"secret-invalid-port\n"])
def test_invalid_file_configuration_reports_error_without_contents(
    configured_parser, monkeypatch, tmp_path, capsys, contents,
):
    monkeypatch.setenv("MQTT_HOST", "host")
    path = tmp_path / "port"
    if contents is not None:
        path.write_bytes(contents)
    monkeypatch.setenv("MQTT_PORT_FILE", str(path))
    with pytest.raises(SystemExit) as exc:
        parse_configuration(configured_parser)
    assert exc.value.code == 2
    error = capsys.readouterr().err
    assert "MQTT_PORT_FILE" in error
    assert "secret-invalid-port" not in error


def test_file_preserves_non_newline_whitespace(configured_parser, monkeypatch, tmp_path):
    path = tmp_path / "host"
    path.write_text(" host \n", encoding="utf-8")
    monkeypatch.setenv("MQTT_HOST_FILE", str(path))
    assert parse_configuration(configured_parser).mqtt_host == " host "
