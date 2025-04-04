from pymodbus.payload import BinaryPayloadBuilder
from pymodbus.constants import Endian
from typing import Optional
from enum import IntEnum, StrEnum


class StringEnum(StrEnum):
    NotImplementedString = "\x00" * 32  # Placeholder for string fields

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
    NotImplementedBitfield32 = 0xFFFFFFFF
    NotImplementedBitfield16 = 0xFFFF
    NotImplementedBitfield8 = 0xFF
    NotImplementedBitfield4 = 0xF
    NotImplementedBitfield2 = 0x3
    NotImplementedBitfield1 = 0x1

class SunSpecPayloadBuilder(BinaryPayloadBuilder):
    """
    Custom Payload Builder for SunSpec models.
    This class overrides methods to handle default values for missing data.
    """

    def __init__(self, byteorder=Endian.BIG, wordorder=Endian.BIG):
        super().__init__(byteorder=byteorder, wordorder=wordorder)

    def add_uint16(self, value: Optional[int]):
        """
        Add a 16-bit unsigned integer to the payload.
        Use a default value if the input is None.
        """
        super().add_16bit_uint(value if value is not None else NumberEnum.NotImplementedUint16)

    def add_uint32(self, value: Optional[int]):
        """
        Add a 32-bit unsigned integer to the payload.
        Use a default value if the input is None.
        """
        super().add_32bit_uint(value if value is not None else NumberEnum.NotImplementedUint32)

    def add_float32(self, value: Optional[float]):
        """
        Add a 32-bit float to the payload.
        Use a default value (NaN) if the input is None.
        """
        if value is None:
            super().add_32bit_uint(NumberEnum.NotImplementedFloat32)  # NaN in IEEE 754
        else:
            super().add_32bit_float(value)

    def add_bitfield32(self, value: Optional[int]):
        """
        Add a 32-bit bitfield to the payload.
        Use a default value if the input is None.
        """
        super().add_32bit_uint(value if value is not None else NumberEnum.NotImplementedBitfield32)