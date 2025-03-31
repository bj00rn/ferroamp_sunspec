import asyncio
import json
import logging
import argparse
from paho.mqtt import client as mqtt


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


class BaseMqttListener:
    def __init__(self, client_id, broker, port, topic, on_connect=None, on_message=None):
        """
        Initialize the MQTT listener.

        Args:
            client_id (str): The MQTT client ID.
            broker (str): The MQTT broker address.
            port (int): The MQTT broker port.
            on_connect (function): Custom on_connect callback function.
            on_message (function): Custom on_message callback function.
        """
        self.client_id = client_id
        self.broker = broker
        self.port = port
        self.topic = topic
        self.client = mqtt.Client(client_id=client_id)

        # Assign custom callbacks or use default implementations
        self._on_connect = on_connect
        self._on_message = on_message

        # Set up the MQTT client callbacks
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

        # Create an asyncio event loop
        self.loop = asyncio.get_event_loop()

    def connect(self):
        """
        Connect to the MQTT broker.
        """
        log.info(f"Connecting to MQTT broker at {self.broker}:{self.port}...")
        self.client.connect(self.broker, self.port)
        self.client.subscribe(self.topic)

    def on_connect(self, client, userdata, flags, rc):
        """
        Callback for when the client connects to the broker.
        """
        if rc == 0:
            log.info("Successfully connected to MQTT broker.")
        else:
            log.error(f"Failed to connect to MQTT broker. Return code: {rc}")

        # Call the custom on_connect callback if provided
        if self._on_connect:
            asyncio.run_coroutine_threadsafe(
                self._on_connect(client, userdata, flags, rc), self.loop
            )

    def on_message(self, client, userdata, msg):
        """
        Callback for when a message is received.
        """
        log.debug(f"Message received on topic {msg.topic}: {msg.payload.decode()}")
        try:
            # Parse the JSON payload
            data = json.loads(msg.payload.decode())
            log.debug(f"Processed message data: {data}")
        except json.JSONDecodeError as e:
            log.error(f"Failed to decode JSON payload: {e}")

        # Call the custom on_message callback if provided
        if self._on_message:
            asyncio.run_coroutine_threadsafe(
                self._on_message(client, userdata, msg), self.loop
            )

    async def subscribe(self, topic):
        """
        Subscribe to a topic asynchronously.

        Args:
            topic (str): The MQTT topic to subscribe to.
        """
        log.info(f"Subscribing to topic: {topic}")
        await asyncio.get_event_loop().run_in_executor(None, self.client.subscribe, topic)

    async def loop_forever(self):
        """
        Start the loop to process network traffic asynchronously.
        """
        log.info("Starting MQTT loop...")
        await asyncio.get_event_loop().run_in_executor(None, self.client.loop_forever)


class FerroampExtApiListener(BaseMqttListener):
    def __init__(self, client_id, broker, port, topic="extapi/data/ehub", on_connect=None, on_message=None):
        """
        Initialize the FerroampExtApiListener.

        Args:
            client_id (str): The MQTT client ID.
            broker (str): The MQTT broker address.
            port (int): The MQTT broker port.
        """
        super().__init__(client_id, broker, port, topic, on_connect, on_message)


async def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Test the FerroampExtApiListener.")
    parser.add_argument(
        "--broker",
        type=str,
        required=True,
        help="The MQTT broker address (e.g., 'mqtt.example.com').",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=1883,
        help="The MQTT broker port (default: 1883).",
    )
    parser.add_argument(
        "--client_id",
        type=str,
        default="ferroamp_listener",
        help="The MQTT client ID (default: 'ferroamp_listener').",
    )
    parser.add_argument(
        "--topic",
        type=str,
        default="extapi/data/ehub",
        help="The MQTT topic to subscribe to (default: 'extapi/data/ehub').",
    )
    args = parser.parse_args()

    # Initialize the FerroampExtApiListener
    mqtt_listener = FerroampExtApiListener(
        client_id=args.client_id,
        broker=args.broker,
        port=args.port,
    )

    # Connect to the MQTT broker and subscribe to the topic
    mqtt_listener.connect()
    await mqtt_listener.subscribe(args.topic)

    # Start the MQTT loop
    await mqtt_listener.loop_forever()


if __name__ == "__main__":
    asyncio.run(main())