import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar, List
from enum import IntEnum

from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadBuilder

log = logging.getLogger(__name__)  # Create a logger instance

class NumberEnum(IntEnum):
    NotImplementedUint16 = 0xFFFF
    NotImplementedUint32 = 0xFFFFFFFF
    NotImplementedFloat32 = 0x7FC00000  # NaN in IEEE 754
    NotImplementedInt16 = 0x7FFF
    NotImplementedInt32 = 0x7FFFFFFF
    NotImplementedInt8 = 0x7F
    NotImplementedUint8 = 0xFF
    NotImplementedInt64 = 0x7FFFFFFFFFFFFFFF
    NotImplementedUint64 = 0xFFFFFFFFFFFFFFFF
    NotImplementedFloat64 = 0x7FF8000000000000  # NaN in IEEE 754
    NotImplementedString = "\x00" * 32  # Placeholder for string fields
    NotImplementedBitfield32 = 0xFFFFFFFF
    NotImplementedBitfield16 = 0xFFFF
    NotImplementedBitfield8 = 0xFF
    NotImplementedBitfield4 = 0xF
    NotImplementedBitfield2 = 0x3
    NotImplementedBitfield1 = 0x1
@dataclass
class DataModel(ABC):
    """
    Abstract base class for SunSpec data models.
    """
    base_address: int = 40000  # Base address for the model

    registers: List[int] = None  # Holds the precomputed data block

    @abstractmethod
    def get_register(self) -> List[int]:
        """
        Generate and return the data block for the model.
        Must be implemented by subclasses.
        """

    def get_dict(self, base_address) -> dict:
        """
        Convert the data block into a dictionary format.
        """
        data_dict = {
            base_address + i: value for i, value in enumerate(self.registers)
        }
        return data_dict

    def get_address_range(self, start_address):
        """
        Calculate the address range for the model based on its base address and data length.
        """
        return (
            start_address,
            start_address + len(self.registers),
            len(self.registers),
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

    def get_register(self) -> List[int]:
        """
        Generate and return the Common Data Block (Model 1) for the SunSpec server.
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

        return data


class EndModel(DataModel):
    """
    Empty data model for testing purposes.
    """

    ID: ClassVar[int] = 0xFFFF  # End Model ID
    L: ClassVar[int] = 0  # Length of the End Model Block (in registers)

    def get_register(self) -> List[int]:
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
    # Class variable
    ID: ClassVar[int] = 113  # Model ID for Three-Phase Inverter (mandatory)
    L: ClassVar[int] = 60  # Length of the Model 113 Block (in registers) (mandatory)

    # Mandatory fields
    A: float = 0  # AC Current (A) (mandatory, float32)
    AphA: float = 0  # Phase A Current (A) (mandatory, float32)
    AphB: float = 0  # Phase B Current (A) (mandatory, float32)
    AphC: float = 0  # Phase C Current (A) (mandatory, float32)
    PPVphAB: float = 0  # Line-to-Line Voltage AB (V) (mandatory, float32)
    PPVphBC: float = 0  # Line-to-Line Voltage BC (V) (mandatory, float32)
    PPVphCA: float = 0  # Line-to-Line Voltage CA (V) (mandatory, float32)
    PhVphA: float = 0  # Line-to-Neutral Voltage AN (V) (mandatory, float32)
    PhVphB: float = 0  # Line-to-Neutral Voltage BN (V) (mandatory, float32)
    PhVphC: float = 0  # Line-to-Neutral Voltage CN (V) (mandatory, float32)
    W: float = 0  # AC Power (W) (mandatory, float32)
    Hz: float = 0  # AC Frequency (Hz) (mandatory, float32)
    VA: float = 0  # Apparent Power (VA) (mandatory, float32)
    VAr: float = 0  # Reactive Power (VAR) (mandatory, float32)
    PF: float = 0  # Power Factor (mandatory, float32)
    WH: float = 0  # AC Energy (Wh) (mandatory, float32)
    DCA: float = 0  # DC Current (A) (mandatory, float32)
    DCV: float = 0  # DC Voltage (V) (mandatory, float32)
    DCW: float = 0  # DC Power (W) (mandatory, float32)
    TmpCab: float = 0  # Cabinet Temperature (°C) (mandatory, float32)
    TmpSnk: float = 0  # Heat Sink Temperature (°C) (mandatory, float32)
    St: int = 0  # Operating State (mandatory, enum16)
    Evt1: int = 0  # Event Flags 1 (mandatory, bitfield32)
    Evt2: int = 0  # Event Flags 2 (mandatory, bitfield32)

    # Optional fields
    TmpTrns: float = None  # Transformer Temperature (°C) (optional, float32)
    TmpOt: float = None  # Other Temperature (°C) (optional, float32)
    StVnd: int = None  # Vendor-specific Operating State (optional, enum16)
    EvtVnd1: int = None  # Vendor-specific Event Flags 1 (optional, bitfield32)
    EvtVnd2: int = None  # Vendor-specific Event Flags 2 (optional, bitfield32)
    EvtVnd3: int = None  # Vendor-specific Event Flags 3 (optional, bitfield32)
    EvtVnd4: int = None  # Vendor-specific Event Flags 4 (optional, bitfield32)

    def get_register(self) -> list:
        """
        Generate and return the Model 113 Data Block (Three-Phase Inverter).
        """
        builder = BinaryPayloadBuilder(byteorder=Endian.BIG, wordorder=Endian.BIG)

        # Helper for adding 32-bit float fields
        def add_float32(value):
            if value is None:
                builder.add_32bit_uint(NumberEnum.NotImplementedFloat32)  # NaN in IEEE 754
            else:
                builder.add_32bit_float(value)

        # Helper for adding 32-bit uint fields
        def add_uint32(value):
            if value is None:
                builder.add_32bit_uint(NumberEnum.NotImplementedUint32)
            else:
                builder.add_32bit_uint(value)

        # Helper for adding 16-bit uint fields
        def add_uint16(value):
            if value is None:
                builder.add_16bit_uint(NumberEnum.NotImplementedUint16)
            else:
                builder.add_16bit_uint(value)

        # Add Model ID and Length
        add_uint16(self.ID)  # Model ID
        add_uint16(self.L)  # Length of the Model 113 Block (in registers)

        # Add float32 fields
        add_float32(self.A)
        add_float32(self.AphA)
        add_float32(self.AphB)
        add_float32(self.AphC)
        add_float32(self.PPVphAB)
        add_float32(self.PPVphBC)
        add_float32(self.PPVphCA)
        add_float32(self.PhVphA)
        add_float32(self.PhVphB)
        add_float32(self.PhVphC)
        add_float32(self.W)
        add_float32(self.Hz)
        add_float32(self.VA)
        add_float32(self.VAr)
        add_float32(self.PF)
        add_float32(self.WH)
        add_float32(self.DCA)
        add_float32(self.DCV)
        add_float32(self.DCW)
        add_float32(self.TmpCab)
        add_float32(self.TmpSnk)
        add_float32(self.TmpTrns)
        add_float32(self.TmpOt)

        # Add enum16 fields
        add_uint16(self.St)
        add_uint16(self.StVnd)

        # Add bitfield32 fields
        add_uint32(self.Evt1)
        add_uint32(self.Evt2)
        add_uint32(self.EvtVnd1)
        add_uint32(self.EvtVnd2)
        add_uint32(self.EvtVnd3)
        add_uint32(self.EvtVnd4)

        # Convert the payload to a list of registers
        data = builder.to_registers()

        log.debug(f"Model 113 Data Block: {data}, model length: {len(data) - 2}")
        return data
