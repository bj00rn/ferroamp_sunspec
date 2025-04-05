import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar, List, Optional
from enum import IntEnum, StrEnum
from data import FerroampData
from payload import SunSpecPayloadBuilder

from pymodbus.constants import Endian

log = logging.getLogger(__name__)  # Create a logger instance

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

    def update_from_mqtt(self, data: FerroampData):
        """
        Update the model fields from the given MQTT data.
        This method should be implemented by subclasses to handle specific data updates.
        """
        raise NotImplementedError(
            "update_from_mqtt() must be implemented by subclasses"
        )

@dataclass
class CommonModel(DataModel):
    """
    Common Model: Represents the common data block for SunSpec models.
    """
    # Mandatory fields
    Mn: str = "Mnfr Corp"  # Manufacturer
    Md: str = "Invrtr"  # Model
    Opt: str = ""  # Options
    Vr: str = "1"  # Version
    SN: str = "123456789"  # Serial Number
    DA: int = 9999  # Device Address

    # Class variables
    ID: ClassVar[int] = 1  # Model ID for Common Block
    L: ClassVar[int] = 66  # Length of the Common Block (in registers)

    def get_register(self) -> List[int]:
        """
        Generate and return the Common Data Block (Model 1) for the SunSpec server.
        """
        builder = SunSpecPayloadBuilder(byteorder=Endian.BIG, wordorder=Endian.BIG)

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
    
    def update_from_mqtt(self, data: FerroampData):
        pass


class EmptyModel(DataModel):
    """
    End Model: Represents the end of the SunSpec data map
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
    """
    Model 113: Three-Phase Inverter float32 values
    """

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
        builder = SunSpecPayloadBuilder(byteorder=Endian.BIG, wordorder=Endian.BIG)

        # Add Model ID and Length
        builder.add_16bit_uint(self.ID)  # Model ID
        builder.add_16bit_uint(self.L)  # Length of the Model 113 Block (in registers)

        # Add float32 fields
        builder.add_float32(self.A)
        builder.add_float32(self.AphA)
        builder.add_float32(self.AphB)
        builder.add_float32(self.AphC)
        builder.add_float32(self.PPVphAB)
        builder.add_float32(self.PPVphBC)
        builder.add_float32(self.PPVphCA)
        builder.add_float32(self.PhVphA)
        builder.add_float32(self.PhVphB)
        builder.add_float32(self.PhVphC)
        builder.add_float32(self.W)
        builder.add_float32(self.Hz)
        builder.add_float32(self.VA)
        builder.add_float32(self.VAr)
        builder.add_float32(self.PF)
        builder.add_float32(self.WH)
        builder.add_float32(self.DCA)
        builder.add_float32(self.DCV)
        builder.add_float32(self.DCW)
        builder.add_float32(self.TmpCab)
        builder.add_float32(self.TmpSnk)
        builder.add_float32(self.TmpTrns)
        builder.add_float32(self.TmpOt)

        # Add enum16 fields
        builder.add_uint16(self.St)
        builder.add_uint16(self.StVnd)

        # Add bitfield32 fields
        builder.add_uint32(self.Evt1)
        builder.add_uint32(self.Evt2)
        builder.add_uint32(self.EvtVnd1)
        builder.add_uint32(self.EvtVnd2)
        builder.add_uint32(self.EvtVnd3)
        builder.add_uint32(self.EvtVnd4)

        # Convert the payload to a list of registers
        data = builder.to_registers()

        log.debug(f"Model 113 Data Block: {data}, model length: {len(data) - 2}")
        return data

    def update_from_mqtt(self, data: FerroampData):
        """
        Update the model fields from the given MQTT data.
        """
        for key, value in data.items():
            if key == "gridfreq":
                # Update grid frequency
                setattr(self, "Hz", float(value["val"]))
            if key == "iextq":
                # AC Current (A)
                # Is this the correct field?
                setattr(self, "AphA", float(value["L1"]))
                setattr(self, "AphB", float(value["L2"]))
                setattr(self, "AphC", float(value["L3"]))
                setattr(self, "A", float(value["L1"])+float(value["L2"])+float(value["L3"]))
            if key == "ul":
                setattr(self, "PhVphA", float(value["L1"]))
                setattr(self, "PhVphB", float(value["L2"]))
                setattr(self, "PhVphC", float(value["L3"]))
            if key == "pload":
                # AC Power (W)
                setattr(self, "W", float(value["L1"])+float(value["L2"])+float(value["L3"]))
            if key == "sext":
                # Apparent Power (VA)
                setattr(self, "VA", float(value["val"]))
            if key == "winvprodq":
                setattr(self, "WH", float(value["L1"])+float(value["L2"])+float(value["L3"]))


@dataclass
class Model214:
    """
    Model 214: Delta-connect three-phase (abc) meter with float32 values
    """

    # Class variables
    ID: ClassVar[int] = 214  # Model identifier (uint16)
    L: ClassVar[int] = 124  # Model length (uint16, including Model ID and Length fields)

    # Mandatory fields (sorted first)
    A: float = 0  # Total AC Current (float32)
    AphA: float = 0  # Phase A Current (float32)
    AphB: float = 0  # Phase B Current (float32)
    AphC: float = 0  # Phase C Current (float32)
    PPV: float = 0  # Line to Line AC Voltage (float32)
    PhVphAB: float = 0  # Phase Voltage AB (float32)
    PhVphBC: float = 0  # Phase Voltage BC (float32)
    PhVphCA: float = 0  # Phase Voltage CA (float32)
    Hz: float = 0  # Frequency (float32)
    W: float = 0  # Total Real Power (float32)
    TotWhExp: float = 0  # Total Real Energy Exported (float32)
    TotWhImp: float = 0  # Total Real Energy Imported (float32)
    Evt: int = 0  # Meter Event Flags (bitfield32)

    # Optional fields (sorted after mandatory fields)
    PhV: Optional[float] = None  # Line to Neutral AC Voltage (float32)
    PhVphA: Optional[float] = None  # Phase Voltage AN (float32)
    PhVphB: Optional[float] = None  # Phase Voltage BN (float32)
    PhVphC: Optional[float] = None  # Phase Voltage CN (float32)
    WphA: Optional[float] = None  # Watts phase A (float32)
    WphB: Optional[float] = None  # Watts phase B (float32)
    WphC: Optional[float] = None  # Watts phase C (float32)
    VA: Optional[float] = None  # AC Apparent Power (float32)
    VAphA: Optional[float] = None  # VA phase A (float32)
    VAphB: Optional[float] = None  # VA phase B (float32)
    VAphC: Optional[float] = None  # VA phase C (float32)
    VAR: Optional[float] = None  # Reactive Power (float32)
    VARphA: Optional[float] = None  # VAR phase A (float32)
    VARphB: Optional[float] = None  # VAR phase B (float32)
    VARphC: Optional[float] = None  # VAR phase C (float32)
    PF: Optional[float] = None  # Power Factor (float32)
    PFphA: Optional[float] = None  # PF phase A (float32)
    PFphB: Optional[float] = None  # PF phase B (float32)
    PFphC: Optional[float] = None  # PF phase C (float32)
    TotVAhExp: Optional[float] = None  # Total Apparent Energy Exported (float32)
    TotVAhImp: Optional[float] = None  # Total Apparent Energy Imported (float32)
    TotVArhImpQ1: Optional[float] = None  # Total Reactive Energy Imported Q1 (float32)
    TotVArhImpQ2: Optional[float] = None  # Total Reactive Energy Imported Q2 (float32)
    TotVArhExpQ3: Optional[float] = None  # Total Reactive Energy Exported Q3 (float32)
    TotVArhExpQ4: Optional[float] = None  # Total Reactive Energy Exported Q4 (float32)

    # Additional fields from model_214.json
    TotWhExpPhA: Optional[float] = None  # Total Watt-hours Exported phase A (float32)
    TotWhExpPhB: Optional[float] = None  # Total Watt-hours Exported phase B (float32)
    TotWhExpPhC: Optional[float] = None  # Total Watt-hours Exported phase C (float32)
    TotWhImpPhA: Optional[float] = None  # Total Watt-hours Imported phase A (float32)
    TotWhImpPhB: Optional[float] = None  # Total Watt-hours Imported phase B (float32)
    TotWhImpPhC: Optional[float] = None  # Total Watt-hours Imported phase C (float32)
    TotVAhExpPhA: Optional[float] = None  # Total VA-hours Exported phase A (float32)
    TotVAhExpPhB: Optional[float] = None  # Total VA-hours Exported phase B (float32)
    TotVAhExpPhC: Optional[float] = None  # Total VA-hours Exported phase C (float32)
    TotVAhImpPhA: Optional[float] = None  # Total VA-hours Imported phase A (float32)
    TotVAhImpPhB: Optional[float] = None  # Total VA-hours Imported phase B (float32)
    TotVAhImpPhC: Optional[float] = None  # Total VA-hours Imported phase C (float32)
    TotVArhImpQ1phA: Optional[float] = None  # Total VAr-hours Imported Q1 phase A (float32)
    TotVArhImpQ1phB: Optional[float] = None  # Total VAr-hours Imported Q1 phase B (float32)
    TotVArhImpQ1phC: Optional[float] = None  # Total VAr-hours Imported Q1 phase C (float32)
    TotVArhImpQ2phA: Optional[float] = None  # Total VAr-hours Imported Q2 phase A (float32)
    TotVArhImpQ2phB: Optional[float] = None  # Total VAr-hours Imported Q2 phase B (float32)
    TotVArhImpQ2phC: Optional[float] = None  # Total VAr-hours Imported Q2 phase C (float32)
    TotVArhExpQ3phA: Optional[float] = None  # Total VAr-hours Exported Q3 phase A (float32)
    TotVArhExpQ3phB: Optional[float] = None  # Total VAr-hours Exported Q3 phase B (float32)
    TotVArhExpQ3phC: Optional[float] = None  # Total VAr-hours Exported Q3 phase C (float32)
    TotVArhExpQ4phA: Optional[float] = None  # Total VAr-hours Exported Q4 phase A (float32)
    TotVArhExpQ4phB: Optional[float] = None  # Total VAr-hours Exported Q4 phase B (float32)
    TotVArhExpQ4phC: Optional[float] = None  # Total VAr-hours Exported Q4 phase C (float32)

    def get_register(self) -> list:
        """
        Generate and return the Model 214 Data Block (Delta-connect three-phase meter with float32 values).
        """
        builder = SunSpecPayloadBuilder(byteorder=Endian.BIG, wordorder=Endian.BIG)

        # Add Model ID and Length (not included in the length calculation)
        builder.add_16bit_uint(self.ID)  # Model ID
        builder.add_16bit_uint(self.L)  # Model Length (in registers)

        # length should be 2

        # Add mandatory fields 26 registers
        builder.add_float32(self.A)
        builder.add_float32(self.AphA)
        builder.add_float32(self.AphB)
        builder.add_float32(self.AphC)
        builder.add_float32(self.PPV)
        builder.add_float32(self.PhVphAB)
        builder.add_float32(self.PhVphBC)
        builder.add_float32(self.PhVphCA)
        builder.add_float32(self.Hz)
        builder.add_float32(self.W)
        builder.add_float32(self.TotWhExp)
        builder.add_float32(self.TotWhImp)
        builder.add_bitfield32(self.Evt)

    
        # Add 25 optional fields = 50 registers
        builder.add_float32(self.PhV)
        builder.add_float32(self.PhVphA)
        builder.add_float32(self.PhVphB)
        builder.add_float32(self.PhVphC)
        builder.add_float32(self.WphA)
        builder.add_float32(self.WphB)
        builder.add_float32(self.WphC)
        builder.add_float32(self.VA)
        builder.add_float32(self.VAphA)
        builder.add_float32(self.VAphB)
        builder.add_float32(self.VAphC)
        builder.add_float32(self.VAR)
        builder.add_float32(self.VARphA)
        builder.add_float32(self.VARphB)
        builder.add_float32(self.VARphC)
        builder.add_float32(self.PF)
        builder.add_float32(self.PFphA)
        builder.add_float32(self.PFphB)
        builder.add_float32(self.PFphC)
        builder.add_float32(self.TotVAhExp)
        builder.add_float32(self.TotVAhImp)
        builder.add_float32(self.TotVArhImpQ1)
        builder.add_float32(self.TotVArhImpQ2)
        builder.add_float32(self.TotVArhExpQ3)
        builder.add_float32(self.TotVArhExpQ4)

        # Add missing fields
        builder.add_float32(self.TotWhExpPhA)
        builder.add_float32(self.TotWhExpPhB)
        builder.add_float32(self.TotWhExpPhC)
        builder.add_float32(self.TotWhImpPhA)
        builder.add_float32(self.TotWhImpPhB)
        builder.add_float32(self.TotWhImpPhC)
        builder.add_float32(self.TotVAhExpPhA)
        builder.add_float32(self.TotVAhExpPhB)
        builder.add_float32(self.TotVAhExpPhC)
        builder.add_float32(self.TotVAhImpPhA)
        builder.add_float32(self.TotVAhImpPhB)
        builder.add_float32(self.TotVAhImpPhC)
        builder.add_float32(self.TotVArhImpQ1phA)
        builder.add_float32(self.TotVArhImpQ1phB)
        builder.add_float32(self.TotVArhImpQ1phC)
        builder.add_float32(self.TotVArhImpQ2phA)
        builder.add_float32(self.TotVArhImpQ2phB)
        builder.add_float32(self.TotVArhImpQ2phC)
        builder.add_float32(self.TotVArhExpQ3phA)
        builder.add_float32(self.TotVArhExpQ3phB)
        builder.add_float32(self.TotVArhExpQ3phC)
        builder.add_float32(self.TotVArhExpQ4phA)
        builder.add_float32(self.TotVArhExpQ4phB)
        builder.add_float32(self.TotVArhExpQ4phC)
        
        # Convert the payload to a list of registers
        data = builder.to_registers()
        if len(data) != self.L + 2:  # Include Model ID and Length in the total
            log.warning(
                f"Model 214 Data Block length mismatch: expected {self.L + 2} registers, got {len(data)}"
            )
        return data
    
    def update_from_mqtt(self, data: FerroampData):
        """
        Update the model fields from the given MQTT data.
        """
        # for key, value in data.items():
        #     if key == "gridfreq":
        #         # Update grid frequency
        #         setattr(self, "Hz", float(value["val"]))
        #     if key == "iextq":
        #         # AC Current (A)
        #         # Is this the correct field?
        #         setattr(self, "AphA", float(value["L1"]))
        #         setattr(self, "AphB", float(value["L2"]))
        #         setattr(self, "AphC", float(value["L3"]))
        #         setattr(self, "A", float(value["L1"])+float(value["L2"])+float(value["L3"]))
        #     if key == "ul":
        #         setattr(self, "PhVphA", float(value["L1"]))
        #         setattr(self, "PhVphB", float(value["L2"]))
        #         setattr(self, "PhVphC", float(value["L3"]))
        #     if key == "pload":
        #         # AC Power (W)
        #         setattr(self, "W", float(value["L1"])+float(value["L2"])+float(value["L3"]))
        #     if key == "sext":
        #         # Apparent Power (VA)
        #         setattr(self, "VA", float(value["val"]))
        #     if key == "winvprodq":
        #         setattr(self, "WH", float(value["L1"])+float(value["L2"])+float(value["L3"]))

