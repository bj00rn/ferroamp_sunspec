import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar, List

from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadBuilder

log = logging.getLogger(__name__)  # Create a logger instance


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
    ID: ClassVar[int] = 113  # Model ID for Three-Phase Inverter
    L: ClassVar[int] = 60  # Length of the Model 113 Block (in registers)
    A: float = 0  # AC Current (A)
    AphA: float = 0  # Phase A Current (A)
    AphB: float = 0  # Phase B Current (A)
    AphC: float = 0  # Phase C Current (A)
    PPVphAB: float = 0  # Line-to-Line Voltage AB (V)
    PPVphBC: float = 0  # Line-to-Line Voltage BC (V)
    PPVphCA: float = 0  # Line-to-Line Voltage CA (V)
    PhVphA: float = 0  # Line-to-Neutral Voltage AN (V)
    PhVphB: float = 0  # Line-to-Neutral Voltage BN (V)
    PhVphC: float = 0  # Line-to-Neutral Voltage CN (V)
    W: float = 0  # AC Power (W)
    Hz: float = 0  # AC Frequency (Hz)
    VA: float = 0  # Apparent Power (VA)
    VAr: float = 0  # Reactive Power (VAR)
    PF: float = 0  # Power Factor
    WH: float = 0  # AC Energy (Wh)
    DCA: float = 0  # DC Current (A)
    DCV: float = 0  # DC Voltage (V)
    DCW: float = 0  # DC Power (W)
    TmpCab: float = 0  # Cabinet Temperature (°C)
    TmpSnk: float = 0  # Heat Sink Temperature (°C)
    TmpTrns: float = 0  # Transformer Temperature (°C)
    TmpOt: float = 0  # Other Temperature (°C)
    St: int = 0  # Operating State (enum16)
    StVnd: int = 0  # Vendor-specific Operating State (enum16)
    Evt1: int = 0  # Event Flags 1 (bitfield32)
    Evt2: int = 0  # Event Flags 2 (bitfield32)
    EvtVnd1: int = 0  # Vendor-specific Event Flags 1 (bitfield32)
    EvtVnd2: int = 0  # Vendor-specific Event Flags 2 (bitfield32)
    EvtVnd3: int = 0  # Vendor-specific Event Flags 3 (bitfield32)
    EvtVnd4: int = 0  # Vendor-specific Event Flags 4 (bitfield32)

    def get_register(self) -> list:
        """
        Generate and return the Model 113 Data Block (Three-Phase Inverter).
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
