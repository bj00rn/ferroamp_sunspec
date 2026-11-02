"""Async MQTT transport, independent of telemetry decoding and SunSpec."""

import argparse
import asyncio
from collections.abc import Awaitable, Callable
import logging

import aiomqtt

from configuration import parse_configuration
log = logging.getLogger("ferroamp.mqtt")


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
                    log.info("Connected broker %s:%s", self.broker, self.port)
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
    parser.add_argument(
        "--log-level", type=str.upper, default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
        help="logging threshold (default: INFO)",
    )
    args = parse_configuration(parser)
    logging.basicConfig(level=args.log_level)
    logging.getLogger().setLevel(args.log_level)

    async def on_message(message: aiomqtt.Message) -> None:
        log.info("Message on %s: %r", message.topic, message.payload)

    listener = FerroampExtApiListener(
        broker=args.broker, port=args.port, topic=args.topic, client_id=args.client_id,
    )
    await listener.run(on_message)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
