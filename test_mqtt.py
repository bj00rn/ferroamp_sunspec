import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import aiomqtt
import pytest

import ferroamp_sunspec as application
from device import FerroampDevice
import mqtt
from mqtt import FerroampExtApiListener


def test_real_aiomqtt_client_receives_over_loopback_and_disconnects():
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

        async with await asyncio.start_server(broker, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            task = asyncio.create_task(
                FerroampExtApiListener("127.0.0.1", port, "test").run(on_message),
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


def test_mqtt_raw_delivery_and_cancellation_closes_client(monkeypatch):
    async def scenario():
        message = SimpleNamespace(payload=b"\xff", topic="test")
        client = FakeClient([message])
        factory = Mock(return_value=client)
        monkeypatch.setattr(mqtt.aiomqtt, "Client", factory)
        callback = AsyncMock()
        listener = FerroampExtApiListener("broker.invalid", 1884, "custom", "reader")
        task = asyncio.create_task(listener.run(callback))
        try:
            await asyncio.wait_for(client.waiting.wait(), timeout=1)
            factory.assert_called_once_with(
                hostname="broker.invalid", port=1884, identifier="reader",
            )
            client.subscribe.assert_awaited_once_with("custom")
            callback.assert_awaited_once_with(message)
        finally:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        assert client.closed

    asyncio.run(scenario())


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
    (b'{"pload":{"L1":"100","L2":"200","L3":"300"}}', 600),
    (b'{"gridfreq":{"val":"50"},"pload":{"L1":"100"}}', None),
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
    if expected_power is None:
        assert device.models[113][0].Hz.value is None
        assert "Rejected MQTT message" in caplog.text
