import asyncio
import logging
import argparse
from paho.mqtt import client as mqtt


log = logging.getLogger(__name__)


class BaseMqttListener:
    def __init__(self, broker, port, topic, on_connect=None, on_message=None):
        """
        Initialize the MQTT listener.

        Args:
            broker (str): The MQTT broker address.
            port (int): The MQTT broker port.
            on_connect (function): Custom on_connect callback function.
            on_message (function): Custom on_message callback function.
        """
        self.broker = broker
        self.port = port
        self.topic = topic
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

        # Assign custom callbacks or use default implementations
        self._on_connect = on_connect
        self._on_message = on_message

        # Set up the MQTT client callbacks
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

    def connect(self):
        """
        Connect to the MQTT broker.
        """
        log.info(f"Connecting to MQTT broker at {self.broker}:{self.port}...")
        result = self.client.connect(self.broker, self.port)
        if result != mqtt.MQTT_ERR_SUCCESS:
            raise ConnectionError(f"MQTT connect failed: {mqtt.error_string(result)}")

    def on_connect(self, client, userdata, flags, reason_code, properties):
        """
        Callback for when the client connects to the broker.
        """
        if reason_code.is_failure:
            log.error("MQTT connection rejected: %s; the network loop will retry", reason_code)
        else:
            result, _ = client.subscribe(self.topic)
            if result != mqtt.MQTT_ERR_SUCCESS:
                raise ConnectionError(f"MQTT subscribe failed: {mqtt.error_string(result)}")
            # we should always subscribe from on_connect callback to be sure
            # our subscribed is persisted across reconnections.
        
        # Call the custom on_connect callback if provided
        if self._on_connect:
            self._on_connect(client, userdata, flags, reason_code, properties)

    def on_message(self, client, userdata, msg):
        """
        Callback for when a message is received.
        """
        if self._on_message:
            self._on_message(client, userdata, msg)

    async def subscribe(self, topic):
        """
        Subscribe to a topic asynchronously.

        Args:
            topic (str): The MQTT topic to subscribe to.
        """
        log.info(f"Subscribing to topic: {topic}")
        result, _ = await asyncio.to_thread(self.client.subscribe, topic)
        if result != mqtt.MQTT_ERR_SUCCESS:
            raise ConnectionError(f"MQTT subscribe failed: {mqtt.error_string(result)}")

    async def loop_forever(self):
        """
        Start the loop to process network traffic asynchronously.
        """
        log.info("Starting MQTT loop...")
        try:
            result = await asyncio.to_thread(self.client.loop_forever)
            if result != mqtt.MQTT_ERR_SUCCESS:
                raise ConnectionError(f"MQTT loop failed: {mqtt.error_string(result)}")
        finally:
            self.client.disconnect()


class FerroampExtApiListener(BaseMqttListener):
    def __init__(self, broker, port, topic="extapi/data/ehub", on_connect=None, on_message=None):
        """
        Initialize the FerroampExtApiListener.

        Args:
            client_id (str): The MQTT client ID.
            broker (str): The MQTT broker address.
            port (int): The MQTT broker port.
        """
        super().__init__(broker, port, topic, on_connect, on_message)


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
        broker=args.broker,
        port=args.port,
        topic=args.topic,
    )

    # Connect to the MQTT broker and subscribe to the topic
    await asyncio.to_thread(mqtt_listener.connect)

    # Start the MQTT loop
    await mqtt_listener.loop_forever()


if __name__ == "__main__":
    asyncio.run(main())