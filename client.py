import argparse
import json
import logging
import time

from sunspec2.modbus.client import SunSpecModbusClientDeviceTCP
from sunspec2.modbus.modbus import ModbusClientTimeout

# Configure the logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",  # Log format
    datefmt="%Y-%m-%d %H:%M:%S",  # Date format
)
log = logging.getLogger(__name__)  # Create a logger instance


def read_sunspec_inverter(ip, port=502, retries=3, delay=2):
    """
    Connect to a SunSpec inverter using SunSpecModbusClientDeviceTCP and read data.
    Retries the connection in case of failure.
    """
    attempt = 0
    while attempt < retries:
        try:
            # Create a SunSpec Modbus TCP client device
            device = SunSpecModbusClientDeviceTCP(ipaddr=ip, ipport=port, slave_id=1)
            # Scan for SunSpec models
            device.base_addr_list = [40000]
            device.scan()
            if not device.models:
                log.error("No SunSpec models found on the device.")
                return
            log.info(f"Connected to SunSpec device at {ip}:{port}")
            device.get_dict()
            # keep the client and print data
            from time import sleep
            try:
                while True:
                    sleep(1)
                    device.scan()
                    print(json.dumps(device.get_dict(), indent=2))
            except KeyboardInterrupt:
                log.info("Server stopped by user.")
                raise

        except ModbusClientTimeout:
            raise
        except Exception as e:
            if str(e).startswith("Connection error"):
                attempt += 1
                log.warning(f"Attempt {attempt} failed: {e}")
                if attempt < retries:
                    log.info(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
                else:
                    log.error("All retry attempts failed. Exiting.")
            else:
                log.error(f"An error occurred: {e}")         
        finally:
            device.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Read data from a SunSpec inverter.")
    parser.add_argument("ip", help="IP address of the inverter")
    parser.add_argument(
        "--port", type=int, default=502, help="Port number (default: 502)"
    )
    parser.add_argument(
        "--retries", type=int, default=3, help="Number of retry attempts (default: 3)"
    )
    parser.add_argument(
        "--delay",
        type=int,
        default=2,
        help="Delay between retries in seconds (default: 2)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )

    args = parser.parse_args()
    logging.getLogger().setLevel(args.log_level.upper())
    read_sunspec_inverter(args.ip, args.port, args.retries, args.delay)
