import argparse
from abc import ABC, abstractmethod
from dataclasses import dataclass
from threading import Timer
from typing import Dict, List

from pymodbus.datastore import ModbusServerContext, ModbusSlaveContext
from pymodbus.datastore.store import ModbusSequentialDataBlock, ModbusSparseDataBlock
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.server import StartTcpServer


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
        return (start_address, start_address + len(self.get_data()), len(self.get_data()))

@dataclass
class CommonModel(DataModel):
    well_known_manufacturer: str = "Mnfr Corp"
    model: str = "Invrtr"
    version: str = "1"
    options: str = ""
    serial_number: str = "123456789"

    def get_data(self) -> List[int]:
        """
        Generate and return the Common Data Block (Model 1) for the SunSpec server.
        Converts strings to 16-bit integers and pads them to fit SunSpec requirements.

        Returns:
            List[int, int]: List representing the Common Data Block.
        """
        # Convert strings to 16-bit integers and pad them
        manufacturer_ascii = string_to_padded_utf8_array(
            self.well_known_manufacturer, 16
        )
        model_ascii = string_to_padded_utf8_array(self.model, 16)
        options_ascii = string_to_padded_utf8_array(self.options, 8)
        version_ascii = string_to_padded_utf8_array(self.version, 8)
        serial_number_ascii = string_to_padded_utf8_array(self.serial_number, 16)

        # Define the data dictionary
        return [
            0x5375,  # SunSpec ID (fixed value: "SunS" in ASCII)
            0x6E53,  # SunSpec ID continued
            1,  # Model ID (1 for Common Block)
            66,  # Length of the Common Block (in registers)
            *manufacturer_ascii,
            *model_ascii,
            *options_ascii,
            *version_ascii,
            *serial_number_ascii,
            9999,  # device address
            0,  # pad
        ]    

class EndModel(DataModel):
    """
    Empty data model for testing purposes.
    """

    def get_data(self) -> List[int]:
        """
        Return an empty data block.
        """
        return [
            0xFFFF,  # SunSpec End Model ID
            0, # length
        ]


@dataclass
class Model113(DataModel):
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
        data = [
            113,  # Model ID (113 for Three-Phase Inverter)
            60,   # Static Length of the Model 113 Block (in registers)
            *encode_float32(self.A),  # AC Current (float32)
            *encode_float32(self.AphA),  # Phase A Current (float32)
            *encode_float32(self.AphB),  # Phase B Current (float32)
            *encode_float32(self.AphC),  # Phase C Current (float32)
            *encode_float32(self.PPVphAB),  # Phase Voltage AB (float32)
            *encode_float32(self.PPVphBC),  # Phase Voltage BC (float32)
            *encode_float32(self.PPVphCA),  # Phase Voltage CA (float32)
            *encode_float32(self.PhVphA),  # Phase Voltage AN (float32)
            *encode_float32(self.PhVphB),  # Phase Voltage BN (float32)
            *encode_float32(self.PhVphC),  # Phase Voltage CN (float32)
            *encode_float32(self.W),  # AC Power (float32)
            *encode_float32(self.Hz),  # Line Frequency (float32)
            *encode_float32(self.VA),  # Apparent Power (float32)
            *encode_float32(self.VAr),  # Reactive Power (float32)
            *encode_float32(self.PF),  # Power Factor (float32)
            *encode_float32(self.WH),  # AC Energy (float32)
            *encode_float32(self.DCA),  # DC Current (float32)
            *encode_float32(self.DCV),  # DC Voltage (float32)
            *encode_float32(self.DCW),  # DC Power (float32)
            *encode_float32(self.TmpCab),  # Cabinet Temperature (float32)
            *encode_float32(self.TmpSnk),  # Heat Sink Temperature (float32)
            *encode_float32(self.TmpTrns),  # Transformer Temperature (float32)
            *encode_float32(self.TmpOt),  # Other Temperature (float32)
            self.St,  # Operating State (enum16)
            self.StVnd,  # Vendor-specific Operating State (enum16)
            *split_bitfield32(self.Evt1),  # Event Flags 1 (bitfield32)
            *split_bitfield32(self.Evt2),  # Event Flags 2 (bitfield32)
            *split_bitfield32(self.EvtVnd1),  # Vendor Event Flags 1 (bitfield32)
            *split_bitfield32(self.EvtVnd2),  # Vendor Event Flags 2 (bitfield32)
            *split_bitfield32(self.EvtVnd3),  # Vendor Event Flags 3 (bitfield32)
            *split_bitfield32(self.EvtVnd4),  # Vendor Event Flags 4 (bitfield32)
        ]

        print(f"AC Current: {encode_float32(self.A)} (2 registers)")
        print(f"Phase A Current: {encode_float32(self.AphA)} (2 registers)")
        print(f"Event Flags 1: {split_bitfield32(self.Evt1)} (2 registers)")
        print(f"Operating State: {self.St} (1 register)")

        print(f"Model 113 Data Block: {data}, model length: {len(data) - 2}")

        print("Model 113 Data Block (Detailed):")
        for i, value in enumerate(data):
            print(f"Register {i}: {value}")
        print(f"Model 113 Data Block Length (excluding ID and Length): {len(data) - 2}")
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
    inverter_start, inverter_end, inverter_length = Model113().get_adress_range(common_end)
    end_model_start, end_model_end, endmodel_length = EndModel().get_adress_range(inverter_end)
    
    print (f"Common Model: {common_start} - {common_end}, length: {common_length}")
    print (f"Inverter Model: {inverter_start} - {inverter_end}, length: {inverter_length}")
    print (f"End Model: {end_model_start} - {end_model_end}, length: {endmodel_length}")
    

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


def encode_float32(value):
    import struct
    packed = struct.pack(">f", value)
    high = int.from_bytes(packed[:2], "big") or 0
    low = int.from_bytes(packed[2:], "big") or 0
    print(f"Encoding float32: {value} -> [{high}, {low}]")
    return [high, low]


def split_bitfield32(value: int) -> list:
    """
    Split a 32-bit integer into two 16-bit integers (high and low).

    Args:
        value (int): The 32-bit integer to split.

    Returns:
        list: A list containing the high and low 16-bit integers.
    """
    high = (value >> 16) & 0xFFFF  # Extract the high 16 bits
    low = value & 0xFFFF           # Extract the low 16 bits
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
