import argparse

import pytest

from configuration import parse_configuration


@pytest.fixture
def configured_parser(monkeypatch):
    for key in ("MQTT_HOST", "MQTT_PORT", "TRACE_MODBUS", "LOG_LEVEL"):
        monkeypatch.delenv(key, raising=False)
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
