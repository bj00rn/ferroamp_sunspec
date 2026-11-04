import asyncio
import logging
import ssl
import shutil
import subprocess
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import aiomqtt
import pytest

from ferroamp_sunspec import bridge as application
from ferroamp_sunspec.device import FerroampDevice
from ferroamp_sunspec import mqtt
from ferroamp_sunspec.mqtt import FerroampExtApiListener
from ferroamp_sunspec.bridge import PointFreshness
from ferroamp_sunspec.server import SunspecServer


@pytest.mark.parametrize("level", ["debug", "WARNING"])
def test_mqtt_log_level_argument(monkeypatch, level):
    root = logging.getLogger()
    monkeypatch.setattr(root, "level", root.level)
    monkeypatch.setattr("sys.argv", [
        "mqtt.py", "--broker", "test", "--log-level", level,
    ])
    run = AsyncMock()
    monkeypatch.setattr(FerroampExtApiListener, "run", run)
    asyncio.run(mqtt.main())
    assert root.getEffectiveLevel() == getattr(logging, level.upper())
    run.assert_awaited_once()


def test_listener_info_logging_is_independent_of_aiomqtt(caplog):
    with caplog.at_level(logging.INFO):
        assert logging.getLogger("mqtt").getEffectiveLevel() == logging.WARNING
        mqtt.log.info("Listener connected")
    assert "Listener connected" in caplog.text


def test_point_freshness_expires_per_point_and_recovers_on_update(caplog):
    class Clock:
        now = 0.0

        def __call__(self):
            return self.now

    clock = Clock()
    device = FerroampDevice()
    freshness = PointFreshness(device, timeout=5, clock=clock)
    freshness.publish({113: {"W": 500}, 213: {"W": 11000}})

    clock.now = 4
    freshness.publish({113: {"W": 600}})
    clock.now = 5
    assert freshness.expire() == [(213, "W")]
    assert device.models[113][0].W.value == 600
    assert device.models[213][0].W.value is None
    assert freshness.expire() == []

    freshness.publish({213: {"W": 10800}})
    assert device.models[213][0].W.value == 10800
    assert (213, "W") not in freshness.expired
    assert "213.W" in caplog.text


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf")])
def test_point_freshness_requires_positive_finite_timeout(timeout):
    with pytest.raises(ValueError, match="positive finite"):
        PointFreshness(FerroampDevice(), timeout)


def test_modbus_warns_only_for_reads_overlapping_expired_points(caplog):
    device = FerroampDevice()
    now = [0.0]
    freshness = PointFreshness(device, timeout=5, clock=lambda: now[0])
    server = SunspecServer(device, unit_id=7, stale_points=freshness.expired)
    model = device.models[213][0]
    address = model.model_addr + model.W.offset
    with caplog.at_level(logging.WARNING):
        server.store.getValues(3, address, 2)
        assert not caplog.records
        freshness.publish({213: {"W": 11000}})
        server.store.getValues(3, address, 2)
        assert not caplog.records

        now[0] = 5
        freshness.expire()
        caplog.clear()
        server.store.getValues(3, device.base_addr, 2)
        assert not caplog.records
        server.store.getValues(3, address + 1, 1)
        assert len(caplog.records) == 1
        assert (
            f"unit=7 function=3 address={address + 1} count=1 points=213.W"
            in caplog.text
        )
        assert device.models[213][0].W.value is None

        caplog.clear()
        freshness.publish({213: {"W": 10800}})
        server.store.getValues(3, address, 2)
        assert not caplog.records


@pytest.mark.parametrize("tls", [False, True])
def test_real_aiomqtt_client_receives_over_loopback_and_disconnects(tls, tmp_path, monkeypatch):
    server_tls = None
    if tls:
        openssl = shutil.which("openssl")
        if openssl is None:
            pytest.skip("openssl is required to generate a loopback TLS certificate")
        cert = tmp_path / "cert.pem"
        key = tmp_path / "key.pem"
        subprocess.run(
            [openssl, "req", "-x509", "-newkey", "rsa:2048", "-nodes",
             "-keyout", str(key), "-out", str(cert), "-days", "1",
             "-subj", "/CN=localhost", "-addext", "subjectAltName=DNS:localhost"],
            check=True, capture_output=True,
        )
        server_tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        server_tls.load_cert_chain(cert, key)
        monkeypatch.setenv("SSL_CERT_FILE", str(cert))

    async def scenario():
        received = asyncio.Event()
        disconnected = asyncio.Event()
        broker_result = asyncio.get_running_loop().create_future()

        async def packet(reader):
            header = (await reader.readexactly(1))[0]
            remaining = 0
            multiplier = 1
            while True:
                byte = (await reader.readexactly(1))[0]
                remaining += (byte & 127) * multiplier
                if not byte & 128:
                    break
                multiplier *= 128
            return header, await reader.readexactly(remaining)

        async def broker(reader, writer):
            try:
                header, _ = await packet(reader)
                assert header == 0x10  # CONNECT
                writer.write(b"\x20\x02\x00\x00")
                await writer.drain()
                header, body = await packet(reader)
                assert header == 0x82  # SUBSCRIBE
                assert body[2:] == b"\x00\x04test\x00"
                writer.write(b"\x90\x03" + body[:2] + b"\x00")
                writer.write(b"\x30\x08\x00\x04test{}")
                await writer.drain()
                header, _ = await packet(reader)
                assert header == 0xE0  # DISCONNECT
                disconnected.set()
                broker_result.set_result(None)
            except Exception as exc:
                broker_result.set_exception(exc)
            finally:
                writer.close()
                await writer.wait_closed()

        async def on_message(message):
            assert str(message.topic) == "test"
            assert message.payload == b"{}"
            received.set()

        async with await asyncio.start_server(broker, "127.0.0.1", 0, ssl=server_tls) as server:
            port = server.sockets[0].getsockname()[1]
            task = asyncio.create_task(
                FerroampExtApiListener(
                    "mqtts://localhost" if tls else "mqtt://127.0.0.1", port, "test",
                ).run(on_message),
            )
            try:
                await asyncio.wait_for(received.wait(), timeout=3)
            finally:
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
            await asyncio.wait_for(broker_result, timeout=3)
            assert disconnected.is_set()

    asyncio.run(scenario())


@pytest.mark.parametrize("broker,override,host,port,tls", [
    ("broker.invalid", None, "broker.invalid", 1883, False),
    ("mqtt://broker.invalid", None, "broker.invalid", 1883, False),
    ("mqtts://broker.invalid", None, "broker.invalid", 8883, True),
    ("mqtts://broker.invalid:9883", None, "broker.invalid", 9883, True),
    ("mqtts://broker.invalid:9883", 8884, "broker.invalid", 8884, True),
    ("mqtt://broker.invalid:8883", None, "broker.invalid", 8883, False),
    ("mqtt://[::1]:1884", None, "::1", 1884, False),
])
def test_broker_uri(broker, override, host, port, tls):
    listener = FerroampExtApiListener(broker, override)
    assert listener.broker == host
    assert listener.port == port
    assert (listener.tls_context is not None) == tls
    if tls:
        assert listener.tls_context.verify_mode == ssl.CERT_REQUIRED
        assert listener.tls_context.check_hostname is True


@pytest.mark.parametrize("broker", ["broker.invalid", "mqtt://broker.invalid", "mqtt://broker.invalid:8883"])
@pytest.mark.parametrize("credentials", [
    {"username": "test-user"},
    {"password": "test-password"},
    {"username": "test-user", "password": "test-password"},
    {"username": ""},
    {"password": ""},
])
def test_authentication_requires_tls(broker, credentials):
    with pytest.raises(ValueError, match="MQTT authentication requires TLS"):
        FerroampExtApiListener(broker, **credentials)


@pytest.mark.parametrize("broker", [
    "", "http://broker", "mqtts://", "mqtt://broker:abc", "mqtt://broker:65536",
    "mqtt://broker:0", "mqtt://user:secret@broker", "mqtt://broker/topic",
    "mqtt://broker?query", "mqtt://broker#fragment", "mqtt://[broken",
    "mqtt://bad host",
])
def test_invalid_broker_uri_does_not_disclose_credentials(broker):
    with pytest.raises(ValueError, match="Invalid MQTT broker address") as exc:
        FerroampExtApiListener(broker)
    assert "secret" not in str(exc.value)


class FakeClient:
    def __init__(self, messages=(), error=None):
        self.payloads = messages
        self.error = error
        self.entered = asyncio.Event()
        self.waiting = asyncio.Event()
        self.closed = False
        self.subscribe = AsyncMock()

    async def __aenter__(self):
        self.entered.set()
        return self

    async def __aexit__(self, *args):
        self.closed = True

    @property
    def messages(self):
        return self.iter_messages()

    async def iter_messages(self):
        for message in self.payloads:
            yield message
        if self.error is not None:
            raise self.error
        self.waiting.set()
        await asyncio.Event().wait()


@pytest.mark.parametrize("username,password", [(None, None), ("test-user", "test-password")])
def test_mqtt_raw_delivery_and_cancellation_closes_client(monkeypatch, username, password):
    async def scenario():
        message = SimpleNamespace(payload=b"\xff", topic="test")
        client = FakeClient([message])
        factory = Mock(return_value=client)
        monkeypatch.setattr(mqtt.aiomqtt, "Client", factory)
        callback = AsyncMock()
        listener = FerroampExtApiListener(
            "mqtts://broker.invalid" if username is not None else "broker.invalid",
            1884, "custom", "reader",
            username=username, password=password,
        )
        task = asyncio.create_task(listener.run(callback))
        try:
            await asyncio.wait_for(client.waiting.wait(), timeout=1)
            factory.assert_called_once_with(
                hostname="broker.invalid", port=1884, identifier="reader",
                tls_context=listener.tls_context,
                username=username, password=password,
            )
            client.subscribe.assert_awaited_once_with("custom")
            callback.assert_awaited_once_with(message)
        finally:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        assert client.closed

    asyncio.run(scenario())


@pytest.mark.parametrize("entrypoint,prefix,host_option", [
    (application, "MQTT_", "--mqtt-host"),
    (mqtt, "", "--broker"),
])
@pytest.mark.parametrize("source", ["cli", "environment", "file"])
def test_authentication_configuration(monkeypatch, tmp_path, entrypoint, prefix, host_option, source):
    argv = ["command", host_option, "mqtts://broker.invalid"]
    for name, value in (("USERNAME", "test-user"), ("PASSWORD", "test-password")):
        key = f"{prefix}{name}"
        monkeypatch.delenv(key, raising=False)
        monkeypatch.delenv(f"{key}_FILE", raising=False)
        if source == "cli":
            argv.extend([f"--{key.lower().replace('_', '-')}", value])
        elif source == "environment":
            monkeypatch.setenv(key, value)
        else:
            path = tmp_path / key
            path.write_text(value + "\n", encoding="utf-8")
            monkeypatch.setenv(f"{key}_FILE", str(path))
    monkeypatch.setattr("sys.argv", argv)
    listener = Mock()
    listener.run = AsyncMock(side_effect=RuntimeError("test stop"))
    factory = Mock(return_value=listener)
    monkeypatch.setattr(entrypoint, "FerroampExtApiListener", factory)
    if entrypoint is application:
        server = Mock(start=AsyncMock(), stop=AsyncMock())
        monkeypatch.setattr(application, "SunspecServer", Mock(return_value=server))
    with pytest.raises(RuntimeError, match="test stop"):
        asyncio.run(entrypoint.main())
    assert factory.call_args.kwargs["username"] == "test-user"
    assert factory.call_args.kwargs["password"] == "test-password"


@pytest.mark.parametrize("failure", ["connect", "subscribe", "receive"])
def test_mqtt_reconnects_and_resubscribes(monkeypatch, caplog, failure):
    async def scenario():
        first = FakeClient(error=aiomqtt.MqttError("lost connection"))
        second = FakeClient()
        factory = Mock(side_effect=[first, second])
        if failure == "connect":
            factory.side_effect = [aiomqtt.MqttError("connect failed"), second]
        elif failure == "subscribe":
            first.subscribe.side_effect = aiomqtt.MqttError("subscribe failed")
        monkeypatch.setattr(mqtt.aiomqtt, "Client", factory)
        retry = AsyncMock()
        monkeypatch.setattr(mqtt.asyncio, "sleep", retry)
        task = asyncio.create_task(FerroampExtApiListener("broker.invalid").run(AsyncMock()))
        try:
            await asyncio.wait_for(second.waiting.wait(), timeout=1)
            retry.assert_awaited_once_with(5)
            second.subscribe.assert_awaited_once_with("extapi/data/ehub")
            if failure != "connect":
                assert first.closed
        finally:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        assert second.closed
        assert "retrying in 5 seconds" in caplog.text

    asyncio.run(scenario())


def test_cancellation_interrupts_reconnect_wait(monkeypatch):
    async def scenario():
        monkeypatch.setattr(
            mqtt.aiomqtt, "Client", Mock(side_effect=aiomqtt.MqttError("offline")),
        )
        retrying = asyncio.Event()

        async def retry(delay):
            retrying.set()
            await asyncio.Event().wait()

        monkeypatch.setattr(mqtt.asyncio, "sleep", retry)
        task = asyncio.create_task(FerroampExtApiListener("broker.invalid").run(AsyncMock()))
        await asyncio.wait_for(retrying.wait(), timeout=1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())


def test_cancellation_interrupts_connection_attempt(monkeypatch):
    async def scenario():
        connecting = asyncio.Event()
        cancelled = asyncio.Event()

        class ConnectingClient:
            async def __aenter__(self):
                connecting.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    cancelled.set()

            async def __aexit__(self, *args):
                pass

        monkeypatch.setattr(mqtt.aiomqtt, "Client", Mock(return_value=ConnectingClient()))
        task = asyncio.create_task(FerroampExtApiListener("broker.invalid").run(AsyncMock()))
        await asyncio.wait_for(connecting.wait(), timeout=1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert cancelled.is_set()

    asyncio.run(scenario())


def test_message_handler_errors_propagate_and_close_client(monkeypatch):
    async def scenario():
        client = FakeClient([SimpleNamespace(payload=b"test")])
        monkeypatch.setattr(mqtt.aiomqtt, "Client", Mock(return_value=client))
        callback = AsyncMock(side_effect=RuntimeError("handler failed"))
        with pytest.raises(RuntimeError, match="handler failed"):
            await FerroampExtApiListener("broker.invalid").run(callback)
        assert client.closed

    asyncio.run(scenario())


@pytest.mark.parametrize("payload,expected_power", [
    (b'{"pinv":{"L1":"100","L2":"200","L3":"300"},'
     b'"pext":{"L1":"-10","L2":"-20","L3":"-30"},'
     b'"winvprodq":{"L1":"3600000","L2":"7200000","L3":"10800000"}}', -600),
    (b'{"gridfreq":{"val":"50"},"pinv":{"L1":"100"}}', None),
    (b'not json', None),
    (b'\xff', None),
    (b'[]', None),
    (None, None),
])
def test_application_wiring_and_cleanup(monkeypatch, caplog, payload, expected_power):
    device = FerroampDevice()
    instances = []

    class Listener:
        def __init__(self, **kwargs):
            self.closed = False
            instances.append(self)

        async def run(self, on_message):
            try:
                await on_message(SimpleNamespace(payload=payload, topic="test"))
                raise RuntimeError("network stopped")
            finally:
                self.closed = True

    class Server:
        def __init__(self, *args, **kwargs):
            self.stopped = False
            instances.append(self)

        async def start(self):
            pass

        async def stop(self):
            self.stopped = True

    monkeypatch.setattr("sys.argv", ["ferroamp_sunspec.py", "--mqtt-host", "broker.invalid"])
    monkeypatch.setattr(application, "FerroampDevice", lambda **kwargs: device)
    monkeypatch.setattr(application, "FerroampExtApiListener", Listener)
    monkeypatch.setattr(application, "SunspecServer", Server)
    with pytest.raises(RuntimeError, match="network stopped"):
        asyncio.run(application.main())
    listener = next(item for item in instances if isinstance(item, Listener))
    server = next(item for item in instances if isinstance(item, Server))
    assert listener.closed
    assert server.stopped
    assert device.models[113][0].W.value == expected_power
    if expected_power == -600:
        assert device.models[113][0].WH.value == 6
    if expected_power is None:
        assert device.models[113][0].Hz.value is None
        assert "Rejected MQTT message" in caplog.text


@pytest.mark.parametrize("send_valid", [True, False])
def test_application_starts_with_unavailable_telemetry_and_cleans_up(monkeypatch, send_valid):
    async def scenario():
        started = asyncio.Event()
        processed = asyncio.Event()
        stopped = asyncio.Event()
        device = FerroampDevice()

        class Listener:
            def __init__(self, **kwargs):
                pass

            async def run(self, on_message):
                assert started.is_set()
                assert device.models[113][0].W.value is None
                assert device.models[213][0].Hz.value is None
                for payload in (b"{}", b'{"unknown":1}', b"invalid"):
                    await on_message(SimpleNamespace(payload=payload, topic="test"))
                    await asyncio.sleep(0)
                    assert device.models[213][0].Hz.value is None
                if send_valid:
                    await on_message(SimpleNamespace(
                        payload=b'{"gridfreq":{"val":"50"}}', topic="test",
                    ))
                    assert device.models[213][0].Hz.value == 50
                processed.set()
                await asyncio.Event().wait()

        class Server:
            def __init__(self, *args, **kwargs):
                pass

            async def start(self):
                started.set()

            async def stop(self):
                stopped.set()

        monkeypatch.setenv("MQTT_HOST", "test")
        monkeypatch.setattr("sys.argv", ["ferroamp_sunspec.py"])
        monkeypatch.setattr(application, "FerroampExtApiListener", Listener)
        monkeypatch.setattr(application, "SunspecServer", Server)
        monkeypatch.setattr(application, "FerroampDevice", lambda **kwargs: device)
        task = asyncio.create_task(application.main())
        try:
            await asyncio.wait_for(processed.wait(), timeout=2)
            assert started.is_set()
        finally:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        assert stopped.is_set()

    asyncio.run(scenario())
