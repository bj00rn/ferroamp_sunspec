import asyncio
import json
import logging
import argparse
import signal
from mqtt import FerroampExtApiListener
from device import FerroampDevice
from server import SunspecServer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


async def main():
    """
    Main program to initialize and run the Ferroamp MQTT listener, device, and Modbus server.
    """
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Run the Ferroamp SunSpec MQTT and Modbus server.")
    parser.add_argument(
        "--mqtt-host",
        type=str,
        required=True,
        help="The MQTT broker address (e.g., 'mqtt.example.com').",
    )
    parser.add_argument(
        "--mqtt-port",
        type=int,
        default=1883,
        help="The MQTT broker port (default: 1883).",
    )
    parser.add_argument(
        "--modbus-port",
        type=int,
        default=502,
        help="The Modbus server port (default: 502).",
    )
    parser.add_argument(
        "--mqtt-topic",
        type=str,
        default="extapi/data/ehub",
        help="The MQTT topic to subscribe to (default: 'extapi/data/ehub').",
    )
    args = parser.parse_args()

    # Create the Ferroamp device
    ferroamp_device = FerroampDevice(base_addr=40000)
    modbus_server = SunspecServer(device=ferroamp_device, port=args.modbus_port)

    # Define the custom on_message callback for the MQTT listener
    def on_message(client, userdata, msg):
        try:
            # Parse the JSON payload
            data = json.loads(msg.payload.decode())
            # update inverter data
            ferroamp_device.models[1].update_from_mqtt(data)
            modbus_server.update_data()
        except Exception as e:
            log.error(f"Failed to process MQTT message: {e}")

    # Create the MQTT listener
    mqtt_listener = FerroampExtApiListener(
        broker=args.mqtt_host,
        port=args.mqtt_port,
        topic=args.mqtt_topic,
        on_connect=None,
        on_message=on_message,
    )

    # Start the MQTT listener and Modbus server
    mqtt_listener.connect()

    # Define a shutdown event
    shutdown_event = asyncio.Event()

    # Signal handler for graceful shutdown
    def handle_shutdown_signal():
        log.info("Shutdown signal received. Cleaning up...")
        shutdown_event.set()

    # Register signal handlers
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, handle_shutdown_signal)

    

    # Create tasks for the Modbus server, MQTT listener, and shutdown event
    tasks = [
        asyncio.create_task(mqtt_listener.loop_forever()),
        asyncio.create_task(modbus_server.run_forever()),
        asyncio.create_task(shutdown_event.wait()),  # Wait for the shutdown signal
    ]

    # Start the MQTT listener and Modbus server
    mqtt_listener.connect()

    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    except asyncio.CancelledError:
        log.info("Tasks cancelled during shutdown.")

    # Perform cleanup
    log.info("Shutting down MQTT listener and Modbus server...")
    mqtt_listener.client.disconnect()
    for task in tasks:
        if not task.done():
            task.cancel()
        await task
    log.info("Shutdown complete.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except asyncio.exceptions.CancelledError:
        log.info("Program terminated by user.")