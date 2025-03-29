import argparse
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from threading import Timer
from typing import ClassVar, Dict, List

from pymodbus.constants import Endian
from pymodbus.datastore import ModbusServerContext, ModbusSlaveContext
from pymodbus.datastore.store import ModbusSequentialDataBlock
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.payload import BinaryPayloadBuilder
from pymodbus.server import StartTcpServer

# Configure the logger
logging.basicConfig(
    level=logging.DEBUG,  # Set the logging level to DEBUG
    format="%(asctime)s - %(levelname)s - %(message)s",  # Log format
    datefmt="%Y-%m-%d %H:%M:%S",  # Date format
)
log = logging.getLogger(__name__)  # Create a logger instance


@dataclass
class DataModel(ABC):
    """
    Abstract base class for SunSpec data models.
    """

    @abstractmethod
    def get_data(self) -> List[int]:
        """
        Generate and return the data block for the model.
        Must be implemented by subclasses.
        """
        pass

    def get_adress_range(self, start_address):
        return (
            start_address,
            start_address + len(self.get_data()),
            len(self.get_data()),
        )


@dataclass
class CommonModel(DataModel):
    Mn: str = "Mnfr Corp"  # Manufacturer
    Md: str = "Invrtr"  # Model
    Opt: str = ""  # Options
    Vr: str = "1"  # Version
    SN: str = "123456789"  # Serial Number
    DA: int = 9999  # Device Address
    ID: ClassVar[int] = 1  # Model ID for Common Block
    L: ClassVar[int] = 66  # Length of the Common Block (in registers)

    def get_data(self) -> List[int]:
        """
        Generate and return the Common Data Block (Model 1) for the SunSpec server.
        Converts strings to 16-bit integers and pads them to fit SunSpec requirements.

        Returns:
            List[int]: List representing the Common Data Block.
        """
        builder = BinaryPayloadBuilder(byteorder=Endian.BIG, wordorder=Endian.BIG)

        # Add SunSpec ID ("SunS" in ASCII)
        builder.add_16bit_uint(0x5375)  # "Su"
        builder.add_16bit_uint(0x6E53)  # "nS"

        # Add Model ID and Length
        builder.add_16bit_uint(self.ID)  # Model ID (1 for Common Block)
        builder.add_16bit_uint(self.L)  # Length of the Common Block (in registers)

        # Add string fields (padded with null characters to SunSpec requirements)
        builder.add_string(
            self.Mn.ljust(32, "\x00")
        )  # Manufacturer (padded to 32 chars)
        builder.add_string(self.Md.ljust(32, "\x00"))  # Model (padded to 32 chars)
        builder.add_string(self.Opt.ljust(16, "\x00"))  # Options (padded to 16 chars)
        builder.add_string(self.Vr.ljust(16, "\x00"))  # Version (padded to 16 chars)
        builder.add_string(
            self.SN.ljust(32, "\x00")
        )  # Serial Number (padded to 32 chars)

        # Add device address and padding
        builder.add_16bit_uint(self.DA)  # Device address
        builder.add_16bit_uint(0)  # Padding

        # Convert the payload to a list of registers
        data = builder.to_registers()
        log.debug(f"Common Model Data Block: {data}, model length: {len(data) - 2}")
        return data


class EndModel(DataModel):
    """
    Empty data model for testing purposes.
    """

    ID: ClassVar[int] = 0xFFFF  # End Model ID
    L: ClassVar[int] = 0  # Length of the End Model Block (in registers)

    def get_data(self) -> List[int]:
        """
        Return an empty data block.
        """
        data = [
            0xFFFF,  # SunSpec End Model ID
            0,  # length
        ]

        log.debug("End Model Data Block: [0xFFFF, 0], length: {len(data) - 2}")
        return data


@dataclass
class Model113(DataModel):
    ID: ClassVar[int] = 113  # Model ID for Three-Phase Inverter
    L: ClassVar[int] = 60  # Length of the Model 113 Block (in registers)
    A: float = 21.7  # AC Current (A)
    AphA: float = 7.2  # Phase A Current (A)
    AphB: float = 7.3  # Phase B Current (A)
    AphC: float = 7.2  # Phase C Current (A)
    PPVphAB: float = 400.0  # Line-to-Line Voltage AB (V)
    PPVphBC: float = 400.0  # Line-to-Line Voltage BC (V)
    PPVphCA: float = 400.0  # Line-to-Line Voltage CA (V)
    PhVphA: float = 230.0  # Line-to-Neutral Voltage AN (V)
    PhVphB: float = 230.0  # Line-to-Neutral Voltage BN (V)
    PhVphC: float = 230.0  # Line-to-Neutral Voltage CN (V)
    W: float = 5000.0  # AC Power (W)
    Hz: float = 50.0  # AC Frequency (Hz)
    VA: float = 5500.0  # Apparent Power (VA)
    VAr: float = 1000.0  # Reactive Power (VAR)
    PF: float = 0.9  # Power Factor
    WH: float = 120000.0  # AC Energy (Wh)
    DCA: float = 12.0  # DC Current (A)
    DCV: float = 400.0  # DC Voltage (V)
    DCW: float = 4800.0  # DC Power (W)
    TmpCab: float = 45.0  # Cabinet Temperature (°C)
    TmpSnk: float = 45.0  # Heat Sink Temperature (°C)
    TmpTrns: float = 50.0  # Transformer Temperature (°C)
    TmpOt: float = 30.0  # Other Temperature (°C)
    St: int = 4  # Operating State (enum16)
    StVnd: int = 1  # Vendor-specific Operating State (enum16)
    Evt1: int = 2  # Event Flags 1 (bitfield32)
    Evt2: int = 2  # Event Flags 2 (bitfield32)
    EvtVnd1: int = 1  # Vendor-specific Event Flags 1 (bitfield32)
    EvtVnd2: int = 2  # Vendor-specific Event Flags 2 (bitfield32)
    EvtVnd3: int = 3  # Vendor-specific Event Flags 3 (bitfield32)
    EvtVnd4: int = 4  # Vendor-specific Event Flags 4 (bitfield32)

    def get_data(self) -> list:
        """
        Generate and return the Model 113 Data Block (Three-Phase Inverter).
        Ensures all values conform to the SunSpec specification.
        """
        builder = BinaryPayloadBuilder(byteorder=Endian.BIG, wordorder=Endian.BIG)

        # Add Model ID and Length
        builder.add_16bit_uint(self.ID)  # Model ID
        builder.add_16bit_uint(self.L)  # Length of the Model 113 Block (in registers)

        # Add float32 fields
        builder.add_32bit_float(self.A)
        builder.add_32bit_float(self.AphA)
        builder.add_32bit_float(self.AphB)
        builder.add_32bit_float(self.AphC)
        builder.add_32bit_float(self.PPVphAB)
        builder.add_32bit_float(self.PPVphBC)
        builder.add_32bit_float(self.PPVphCA)
        builder.add_32bit_float(self.PhVphA)
        builder.add_32bit_float(self.PhVphB)
        builder.add_32bit_float(self.PhVphC)
        builder.add_32bit_float(self.W)
        builder.add_32bit_float(self.Hz)
        builder.add_32bit_float(self.VA)
        builder.add_32bit_float(self.VAr)
        builder.add_32bit_float(self.PF)
        builder.add_32bit_float(self.WH)
        builder.add_32bit_float(self.DCA)
        builder.add_32bit_float(self.DCV)
        builder.add_32bit_float(self.DCW)
        builder.add_32bit_float(self.TmpCab)
        builder.add_32bit_float(self.TmpSnk)
        builder.add_32bit_float(self.TmpTrns)
        builder.add_32bit_float(self.TmpOt)

        # Add enum16 fields
        builder.add_16bit_uint(self.St)
        builder.add_16bit_uint(self.StVnd)

        # Add bitfield32 fields
        builder.add_32bit_uint(self.Evt1)
        builder.add_32bit_uint(self.Evt2)
        builder.add_32bit_uint(self.EvtVnd1)
        builder.add_32bit_uint(self.EvtVnd2)
        builder.add_32bit_uint(self.EvtVnd3)
        builder.add_32bit_uint(self.EvtVnd4)

        # Convert the payload to a list of registers
        data = builder.to_registers()

        log.debug(f"Model 113 Data Block: {data}, model length: {len(data) - 2}")
        return data


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
    common_model = CommonModel().get_data()
    inverter = Model113().get_data()
    end_model = EndModel().get_data()

    common_start, common_end, common_length = CommonModel().get_adress_range(40000)
    inverter_start, inverter_end, inverter_length = Model113().get_adress_range(
        common_end
    )
    end_model_start, end_model_end, endmodel_length = EndModel().get_adress_range(
        inverter_end
    )

    print(f"Common Model: {common_start} - {common_end}, length: {common_length}")
    print(
        f"Inverter Model: {inverter_start} - {inverter_end}, length: {inverter_length}"
    )
    print(f"End Model: {end_model_start} - {end_model_end}, length: {endmodel_length}")

    return common_model + inverter + end_model


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


class Encoder:
    @staticmethod
    def encode_float32(value):
        import struct

        packed = struct.pack(">f", value)
        high = int.from_bytes(packed[:2], "big") or 0
        low = int.from_bytes(packed[2:], "big") or 0
        print(f"Encoding float32: {value} -> [{high}, {low}]")
        return [high, low]

    @staticmethod
    def split_bitfield32(value: int) -> list:
        """
        Split a 32-bit integer into two 16-bit integers (high and low).

        Args:
            value (int): The 32-bit integer to split.

        Returns:
            list: A list containing the high and low 16-bit integers.
        """
        high = (value >> 16) & 0xFFFF  # Extract the high 16 bits
        low = value & 0xFFFF  # Extract the low 16 bits
        print(f"Splitting bitfield32: {value} -> [High: {high or 0}, Low: {low or 0}]")
        return [high or 0, low or 0]


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

    # Generate SunSpec data (Common + Three-Phase Inverter)
    sunspec_data = generate_sunspec_data()

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
        update_inverter_data(data_block)
        Timer(5, periodic_update).start()  # Update every 5 seconds

    # periodic_update()  # Start the periodic update

    # Start the Modbus TCP server
    StartTcpServer(context, identity=identity, address=("0.0.0.0", args.port))
