"""Async MQTT transport, independent of telemetry decoding and SunSpec."""

import argparse
import asyncio
from collections.abc import Awaitable, Callable
import logging

import aiomqtt

log = logging.getLogger(__name__)


class FerroampExtApiListener:
    def __init__(
        self,
        broker: str,
        port: int = 1883,
        topic: str = "extapi/data/ehub",
        client_id: str | None = None,
    ):
        self.broker = broker
        self.port = port
        self.topic = topic
        self.client_id = client_id

    async def run(self, on_message: Callable[[aiomqtt.Message], Awaitable[None]]) -> None:
        """Receive messages until cancelled, reconnecting after MQTT failures."""
        while True:
            try:
                async with aiomqtt.Client(
                    hostname=self.broker,
                    port=self.port,
                    identifier=self.client_id,
                ) as client:
                    await client.subscribe(self.topic)
                    log.info("Subscribed to MQTT topic %s at %s:%s",
                             self.topic, self.broker, self.port)
                    async for message in client.messages:
                        await on_message(message)
            except aiomqtt.MqttError as exc:
                log.warning("MQTT connection failed: %s; retrying in 5 seconds", exc)
                await asyncio.sleep(5)


async def main():
    parser = argparse.ArgumentParser(description="Listen to Ferroamp ExtApi messages.")
    parser.add_argument("--broker", required=True)
    parser.add_argument("--port", type=int, default=1883)
    parser.add_argument("--client_id", default="ferroamp_listener")
    parser.add_argument("--topic", default="extapi/data/ehub")
    args = parser.parse_args()

    async def on_message(message: aiomqtt.Message) -> None:
        log.info("Message on %s: %r", message.topic, message.payload)

    listener = FerroampExtApiListener(
        broker=args.broker, port=args.port, topic=args.topic, client_id=args.client_id,
    )
    await listener.run(on_message)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
