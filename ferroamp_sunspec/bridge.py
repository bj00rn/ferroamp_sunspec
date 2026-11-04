"""Wire the MQTT input adapter to the independent SunSpec TCP server."""

import argparse
import asyncio
import json
import logging
import math
import signal
import time
from collections.abc import Callable, Mapping

import aiomqtt

from .configuration import parse_configuration
from .device import FerroampDevice, PointValue
from .mqtt import FerroampExtApiListener
from .server import SunspecServer
from .telemetry import ehub_points

log = logging.getLogger(__name__)


class PointFreshness:
    def __init__(
        self,
        device: FerroampDevice,
        timeout: float,
        clock: Callable[[], float] = time.monotonic,
    ):
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("stale timeout must be a positive finite number")
        self.device = device
        self.timeout = timeout
        self.clock = clock
        self.last_updated: dict[tuple[int, str], float] = {}
        self.expired: set[tuple[int, str]] = set()

    def publish(self, updates: Mapping[int, Mapping[str, PointValue]]) -> None:
        self.device.update_points(updates)
        now = self.clock()
        recovered = []
        for model_id, points in updates.items():
            for name in points:
                key = (model_id, name)
                self.last_updated[key] = now
                if key in self.expired:
                    self.expired.remove(key)
                    recovered.append(key)
        if recovered:
            log.info("SunSpec telemetry points recovered: %s", self._format(recovered))

    def expire(self) -> list[tuple[int, str]]:
        now = self.clock()
        newly_expired = [
            key for key, updated in self.last_updated.items()
            if now - updated >= self.timeout and key not in self.expired
        ]
        if not newly_expired:
            return []

        updates: dict[int, dict[str, PointValue]] = {}
        for model_id, name in newly_expired:
            updates.setdefault(model_id, {})[name] = None
        self.device.update_points(updates)
        self.expired.update(newly_expired)
        log.warning(
            "SunSpec telemetry points expired after %.1f seconds: %s",
            self.timeout, self._format(newly_expired),
        )
        return newly_expired

    @staticmethod
    def _format(points: list[tuple[int, str]]) -> str:
        return ", ".join(f"{model_id}.{name}" for model_id, name in sorted(points))

    async def monitor(self) -> None:
        interval = min(self.timeout / 4, 1.0)
        while True:
            await asyncio.sleep(interval)
            self.expire()


async def main():
    parser = argparse.ArgumentParser(description="Run the Ferroamp SunSpec MQTT and Modbus server.")
    parser.add_argument("--mqtt-host", required=True, help="hostname or mqtt:// / mqtts:// URI")
    parser.add_argument("--mqtt-port", type=int, help="override URI port (default: 1883, or 8883 for mqtts)")
    parser.add_argument("--mqtt-topic", default="extapi/data/ehub")
    parser.add_argument("--mqtt-username", help="MQTT authentication username")
    parser.add_argument("--mqtt-password", help="MQTT authentication password (prefer MQTT_PASSWORD_FILE)")
    parser.add_argument("--modbus-host", default="0.0.0.0")
    parser.add_argument("--modbus-port", type=int, default=502)
    parser.add_argument("--base-addr", type=int, default=40000)
    parser.add_argument("--unit-id", type=int, default=1)
    parser.add_argument(
        "--log-level", type=str.upper, default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
        help="logging threshold (default: INFO)",
    )
    parser.add_argument(
        "--stale-timeout", type=float, default=5.0,
        help="seconds without a point update before marking it unavailable (default: 5)",
    )
    parser.add_argument(
        "--trace-modbus", action="store_true",
        help="log each Modbus request's unit, function, address, count, and validation result",
    )
    args = parse_configuration(parser)
    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logging.getLogger().setLevel(args.log_level)

    device = FerroampDevice(base_addr=args.base_addr, unit_id=args.unit_id)
    freshness = PointFreshness(device, args.stale_timeout)
    server = SunspecServer(
        device, port=args.modbus_port, host=args.modbus_host, unit_id=args.unit_id,
        trace_modbus=args.trace_modbus,
        stale_points=freshness.expired,
    )

    async def on_message(msg: aiomqtt.Message) -> None:
        try:
            log.debug("Mqtt payload received %s %s..", msg.topic, str(msg.payload))
            if not isinstance(msg.payload, (str, bytes, bytearray)):
                raise ValueError("ExtApi payload must contain JSON text")
            data = json.loads(msg.payload)
            if not isinstance(data, dict):
                raise ValueError("ExtApi payload must be a JSON object")
            freshness.publish(ehub_points(data))
        except ValueError as exc:
            log.warning("Rejected MQTT message on %s: %s", msg.topic, exc)

    listener = FerroampExtApiListener(
        broker=args.mqtt_host,
        port=args.mqtt_port,
        topic=args.mqtt_topic,
        username=args.mqtt_username,
        password=args.mqtt_password,
    )
    shutdown = asyncio.Event()
    loop = asyncio.get_running_loop()
    signals = (signal.SIGINT, signal.SIGTERM)
    for sig in signals:
        loop.add_signal_handler(sig, shutdown.set)

    tasks = []
    try:
        await server.start()
        tasks = [
            asyncio.create_task(listener.run(on_message)),
            asyncio.create_task(freshness.monitor()),
            asyncio.create_task(shutdown.wait()),
        ]
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            task.result()
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await server.stop()
        for sig in signals:
            loop.remove_signal_handler(sig)
        log.info("Shutdown complete")


def cli() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    cli()
