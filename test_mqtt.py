import asyncio
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from paho.mqtt import client as paho

import ferroamp_sunspec as application
from device import FerroampDevice
from mqtt import FerroampExtApiListener


def test_mqtt_subscribes_on_connect_and_reconnect_only():
    listener = FerroampExtApiListener("broker.invalid", 1883)
    listener.client = Mock()
    listener.client.connect.return_value = paho.MQTT_ERR_SUCCESS
    listener.client.subscribe.return_value = (paho.MQTT_ERR_SUCCESS, 1)
    listener.connect()
    listener.client.connect.assert_called_once_with("broker.invalid", 1883)
    listener.client.subscribe.assert_not_called()
    for _ in range(2):
        listener.on_connect(
            listener.client, None, None, SimpleNamespace(is_failure=False), None,
        )
    assert listener.client.subscribe.call_count == 2


def test_mqtt_delivers_raw_message_without_decoding():
    callback = Mock()
    listener = FerroampExtApiListener("broker.invalid", 1883, on_message=callback)
    message = SimpleNamespace(payload=b"\xff", topic="test")
    listener.on_message(listener.client, None, message)
    callback.assert_called_once_with(listener.client, None, message)


def test_mqtt_network_failure_is_not_swallowed():
    listener = FerroampExtApiListener("broker.invalid", 1883)
    listener.client = Mock()
    listener.client.loop_forever.return_value = paho.MQTT_ERR_CONN_LOST
    with pytest.raises(ConnectionError, match="MQTT loop failed"):
        asyncio.run(listener.loop_forever())
    listener.client.disconnect.assert_called_once()


@pytest.mark.parametrize("payload,expected_power", [
    (b'{"pload":{"L1":"100","L2":"200","L3":"300"}}', 600),
    (b'{"gridfreq":{"val":"50"},"pload":{"L1":"100"}}', None),
    (b'not json', None),
    (b'\xff', None),
    (b'[]', None),
])
def test_application_wiring_and_cleanup(monkeypatch, caplog, payload, expected_power):
    device = FerroampDevice()
    instances = []

    class Listener:
        def __init__(self, **kwargs):
            self.on_message = kwargs["on_message"]
            self.client = Mock()
            self.connect = Mock()
            instances.append(self)

        async def loop_forever(self):
            self.on_message(None, None, SimpleNamespace(payload=payload, topic="test"))
            raise RuntimeError("network stopped")

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
    listener.connect.assert_called_once()
    listener.client.disconnect.assert_called_once()
    assert server.stopped
    assert device.models[113][0].W.value == expected_power
    if expected_power is None:
        assert device.models[113][0].Hz.value is None
        assert "Rejected MQTT message" in caplog.text
