"""Async MQTT transport, independent of telemetry decoding and SunSpec."""

import argparse
import asyncio
from collections.abc import Awaitable, Callable
import logging
import ssl
from urllib.parse import urlsplit

import aiomqtt

from .configuration import parse_configuration
log = logging.getLogger("ferroamp.mqtt")


class FerroampExtApiListener:
    def __init__(
        self,
        broker: str,
        port: int | None = None,
        topic: str = "extapi/data/ehub",
        client_id: str | None = None,
        username: str | None = None,
        password: str | None = None,
    ):
        try:
            address = urlsplit(broker if "://" in broker else f"mqtt://{broker}")
            if (
                address.scheme not in ("mqtt", "mqtts")
                or not address.hostname
                or address.username is not None
                or address.password is not None
                or address.path not in ("", "/")
                or address.query
                or address.fragment
                or any(char.isspace() for char in broker)
            ):
                raise ValueError
            uri_port = address.port
            resolved_port = port if port is not None else uri_port
            if resolved_port is not None and not 1 <= resolved_port <= 65535:
                raise ValueError
        except ValueError:
            raise ValueError(
                "Invalid MQTT broker address: use a hostname or mqtt[s]://host[:port] "
                "without credentials, topic, query, or fragment"
            ) from None
        if address.scheme != "mqtts" and (username is not None or password is not None):
            raise ValueError("MQTT authentication requires TLS: use an mqtts:// broker URI")
        self.broker = address.hostname
        self.port = resolved_port if resolved_port is not None else (
            8883 if address.scheme == "mqtts" else 1883
        )
        self.tls_context = ssl.create_default_context() if address.scheme == "mqtts" else None
        self.topic = topic
        self.client_id = client_id
        self.username = username
        self.password = password

    async def run(self, on_message: Callable[[aiomqtt.Message], Awaitable[None]]) -> None:
        """Receive messages until cancelled, reconnecting after MQTT failures."""
        while True:
            try:
                async with aiomqtt.Client(
                    hostname=self.broker,
                    port=self.port,
                    identifier=self.client_id,
                    tls_context=self.tls_context,
                    username=self.username,
                    password=self.password,
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
    parser.add_argument("--broker", required=True, help="hostname or mqtt:// / mqtts:// URI")
    parser.add_argument("--port", type=int, help="override URI port (default: 1883, or 8883 for mqtts)")
    parser.add_argument("--client_id", default="ferroamp_listener")
    parser.add_argument("--topic", default="extapi/data/ehub")
    parser.add_argument("--username", help="MQTT authentication username")
    parser.add_argument("--password", help="MQTT authentication password (prefer PASSWORD_FILE)")
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
        username=args.username, password=args.password,
    )
    await listener.run(on_message)


def cli() -> None:
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    cli()
