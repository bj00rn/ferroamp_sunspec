"""Wire the MQTT input adapter to the independent SunSpec TCP server."""

import argparse
import asyncio
import json
import logging
import signal

from device import FerroampDevice
from mqtt import FerroampExtApiListener
from server import SunspecServer
from telemetry import inverter_points

log = logging.getLogger(__name__)


async def main():
    parser = argparse.ArgumentParser(description="Run the Ferroamp SunSpec MQTT and Modbus server.")
    parser.add_argument("--mqtt-host", required=True)
    parser.add_argument("--mqtt-port", type=int, default=1883)
    parser.add_argument("--mqtt-topic", default="extapi/data/ehub")
    parser.add_argument("--modbus-host", default="0.0.0.0")
    parser.add_argument("--modbus-port", type=int, default=502)
    parser.add_argument("--base-addr", type=int, default=40000)
    parser.add_argument("--unit-id", type=int, default=1)
    args = parser.parse_args()

    device = FerroampDevice(base_addr=args.base_addr, unit_id=args.unit_id)
    server = SunspecServer(
        device, port=args.modbus_port, host=args.modbus_host, unit_id=args.unit_id,
    )

    def on_message(client, userdata, msg):
        try:
            data = json.loads(msg.payload)
            if not isinstance(data, dict):
                raise ValueError("ExtApi payload must be a JSON object")
            device.update_points(inverter_points(data))
        except ValueError as exc:
            log.warning("Rejected MQTT message on %s: %s", msg.topic, exc)

    listener = FerroampExtApiListener(
        broker=args.mqtt_host,
        port=args.mqtt_port,
        topic=args.mqtt_topic,
        on_message=on_message,
    )
    shutdown = asyncio.Event()
    loop = asyncio.get_running_loop()
    signals = (signal.SIGINT, signal.SIGTERM)
    for sig in signals:
        loop.add_signal_handler(sig, shutdown.set)

    tasks = []
    try:
        await server.start()
        await asyncio.to_thread(listener.connect)
        tasks = [
            asyncio.create_task(listener.loop_forever()),
            asyncio.create_task(shutdown.wait()),
        ]
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            task.result()
    finally:
        listener.client.disconnect()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await server.stop()
        for sig in signals:
            loop.remove_signal_handler(sig)
        log.info("Shutdown complete")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    asyncio.run(main())
