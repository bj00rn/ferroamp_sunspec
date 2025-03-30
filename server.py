import argparse
import logging
from threading import Timer

from pymodbus.datastore import ModbusServerContext, ModbusSlaveContext
from pymodbus.datastore.store import ModbusSparseDataBlock, ModbusSequentialDataBlock
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.server import StartTcpServer

from device import FerroampDevice

# Configure the logger
logging.basicConfig(
    level=logging.DEBUG,  # Set the logging level to DEBUG
    format="%(asctime)s - %(levelname)s - %(message)s",  # Log format
    datefmt="%Y-%m-%d %H:%M:%S",  # Date format
)
log = logging.getLogger(__name__)  # Create a logger instance


def update_inverter_data(d_block):
    """
    Update the inverter data in the Modbus datastore to simulate real-time changes.
    """
    import random

    # Generate random values for AC Power and Voltage within a sane range
    new_ac_power = random.randint(4500, 5500)  # AC Power in the range 4500-5500 W
    new_voltage_ab = random.uniform(
        380.0, 420.0
    )  # Voltage AB in the range 380.0-420.0 V

    print(f"Updated AC Power to {new_ac_power} W and Voltage AB to {new_voltage_ab} V")


# Combine the Common and Three-Phase Inverter Data Blocks
def generate_sunspec_data():
    """
    Combine the Common Data Block and Model 111 Data Block into a single dictionary.
    """
    return 


def string_to_padded_utf8_array(input_string, length, padding_char="\x00"):
    """
    Convert a string to a list of 16-bit integers (two bytes per word) and pad it to the specified length.

    Args:
        input_string (str): The string to convert.
        length (int): The desired length of the output list (in 16-bit words).
        padding_char (str): The character to use for padding (default is a null character).

    Returns:
        list: A list of 16-bit integers, padded to the specified length.
    """
    # Convert the string to bytes
    utf8_bytes = input_string.encode("utf-8")

    # Pad the byte array with the padding character
    padding_byte = padding_char.encode("utf-8")
    padded_bytes = utf8_bytes + padding_byte * (length * 2 - len(utf8_bytes))

    # Group bytes into pairs and convert to 16-bit integers
    words = [
        (padded_bytes[i] << 8) + padded_bytes[i + 1]
        for i in range(0, len(padded_bytes[: length * 2]), 2)
    ]

    return words


# Start the SunSpec server
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Start a SunSpec inverter server.")
    parser.add_argument(
        "--port",
        type=int,
        default=502,
        help="Port number to bind the server (default: 502)",
    )
    args = parser.parse_args()

    print(f"Starting SunSpec inverter server on port {args.port}...")

    device = FerroampDevice(base_addr=40000)
    sunspec_data = device.get_registers()
    print(f"Generated SunSpec Data: {sunspec_data}")

    # Create a Modbus datastore
    data_block = ModbusSequentialDataBlock(40001, sunspec_data)
    store = ModbusSlaveContext(di=None, co=None, hr=data_block, ir=None)
    context = ModbusServerContext(slaves=store, single=True)

    # Set up device identification
    identity = ModbusDeviceIdentification()
    identity.VendorName = "SunSpec"
    identity.ProductCode = "Three-Phase Inverter"
    identity.ModelName = "SunSpec Inverter Model 111"
    identity.MajorMinorRevision = "1.0"

    # Periodically update the inverter data
    def periodic_update():
        from random import random
        # Simulate real-time data updates
        device.models[1].A = random()*100  # Simulate AC current
        data_block.setValues(4001, device.get_registers())
        Timer(5, periodic_update).start()  # Update every 5 seconds

    periodic_update()  # Start the periodic update

    # Start the Modbus TCP server
    StartTcpServer(context, identity=identity, address=("0.0.0.0", args.port))

    log.info(f"Server started. Press Ctrl+C to stop.")

    # Keep the server running""
    try:
        while True:
            from time import sleep
            sleep(1)
    except KeyboardInterrupt:
        log.info("Server stopped by user.")
        pass
    except Exception as e:
        log.error(f"Server stopped due to an error: {e}")
        pass
    finally:
        log.info("Cleaning up and shutting down the server.")
        pass
        # Close the server context
        context.close()
        log.info("Server context closed.")
        pass