import pytest
from pymodbus.constants import Endian
from payload import SunSpecPayloadBuilder, NumberEnum


# Ensure the file is named `test_payload.py` and resides in a directory pytest can discover.
# Verify pytest configuration (e.g., pytest.ini, pyproject.toml, or setup.cfg) includes the test directory.


@pytest.fixture
def builder():
    return SunSpecPayloadBuilder(byteorder=Endian.BIG, wordorder=Endian.BIG)


def test_add_uint16(builder):
    builder.add_uint16(12345)
    builder.add_uint16(None)
    payload = builder.to_registers()
    assert payload == [12345, NumberEnum.NotImplementedUint16]
    assert len(payload) == 2  # Each uint16 adds one register


def test_add_uint16_length(builder):
    builder.add_uint16(12345)
    builder.add_uint16(None)
    payload = builder.to_registers()
    assert len(payload) == 2  # Each uint16 adds one register


def test_add_uint32(builder):
    builder.add_uint32(123456789)
    builder.add_uint32(None)
    payload = builder.to_registers()
    assert payload == [0x075B, 0xCD15, 0xFFFF, 0xFFFF]
    assert len(payload) == 4  # Each uint32 adds two registers


def test_add_uint32_length(builder):
    builder.add_uint32(123456789)
    builder.add_uint32(None)
    payload = builder.to_registers()
    assert len(payload) == 4  # Each uint32 adds two registers


def test_add_float32(builder):
    builder.add_float32(123.456)
    builder.add_float32(None)
    payload = builder.to_registers()
    assert payload[:2] == [0x42F6, 0xE979]  # IEEE 754 representation of 123.456
    assert payload[2:] == [0x7FC0, 0x0000]  # NaN in IEEE 754
    assert len(payload) == 4  # Each float32 adds two registers


def test_add_float32_length(builder):
    builder.add_float32(123.456)
    builder.add_float32(None)
    payload = builder.to_registers()
    assert len(payload) == 4  # Each float32 adds two registers


def test_add_bitfield32(builder):
    builder.add_bitfield32(0b10101010101010101010101010101010)
    builder.add_bitfield32(None)
    payload = builder.to_registers()
    assert payload == [0xAAAA, 0xAAAA, 0xFFFF, 0xFFFF]


def test_add_bitfield32_length(builder):
    builder.add_bitfield32(0b10101010101010101010101010101010)
    builder.add_bitfield32(None)
    payload = builder.to_registers()
    assert len(payload) == 4  # Each bitfield32 adds two registers

def test_wierd_case(builder):

    n = 26

    for i in range(n):
        builder.add_float32(None)

    # Assert payload length
    payload = builder.to_registers()
    assert len(payload) == n * 2  # Each float32 adds two registers, 28 * 2 = 56
