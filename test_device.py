import struct
from concurrent.futures import ThreadPoolExecutor

import pytest
from sunspec2 import device as sunspec

from ferroamp_sunspec.device import FerroampDevice, SunspecDevice


def decode_model(device, model_id):
    model = device.models[model_id][0]
    offset = model.model_addr - device.base_addr
    words = device.get_registers()[offset:offset + model.len]
    return sunspec.Model(model_id=model_id, data=struct.pack(f">{len(words)}H", *words))


def test_model_chain_uses_library_layouts():
    device = FerroampDevice()
    words = device.get_registers()
    assert words[:2] == [0x5375, 0x6E53]
    offset = 2
    for model_id in (1, 113, 213):
        reference = sunspec.Model(model_id=model_id)
        assert words[offset:offset + 2] == [model_id, reference.L.value]
        assert device.models[model_id][0].model_addr == device.base_addr + offset
        assert reference.len == reference.L.value + 2
        offset += reference.len
    assert words[offset:] == [0xFFFF, 0]
    assert len(words) == 260
    assert decode_model(device, 1).Mn.value == "Ferroamp"
    assert decode_model(device, 1).DA.value == 1
    assert 701 not in device.models


def test_unavailable_values_use_library_sentinels():
    device = FerroampDevice()
    inverter = device.models[113][0]
    offset = inverter.model_addr - device.base_addr
    words = device.get_registers()
    assert words[offset + inverter.W.offset:offset + inverter.W.offset + 2] == [0x7FC0, 0]
    assert words[offset + inverter.St.offset] == 0xFFFF
    assert words[offset + inverter.Evt1.offset:offset + inverter.Evt1.offset + 2] == [0xFFFF, 0xFFFF]
    assert decode_model(device, 113).W.value is None
    assert decode_model(device, 113).Evt1.value is None
    assert decode_model(device, 213).TotWhImp.value is None


def test_float_point_updates_use_library_model_offsets():
    device = FerroampDevice()
    device.update_points({
        113: {"W": 4321.5, "St": 4, "Evt1": 0, "Hz": 50},
        213: {"W": -100, "TotWhImp": 12345, "PPVphAB": 400, "Evt": 2},
    })
    inverter = decode_model(device, 113)
    meter = decode_model(device, 213)
    assert inverter.W.value == 4321.5
    assert inverter.St.value == 4
    assert inverter.Evt1.value == 0
    assert inverter.Hz.value == 50
    assert meter.W.value == -100
    assert meter.TotWhImp.value == 12345
    assert meter.PPVphAB.value == 400
    assert meter.Evt.value == 2
    assert meter.PhV.value is None


def test_partial_updates_and_explicit_unavailable():
    device = FerroampDevice()
    device.update_points({113: {"W": 100, "Hz": 50}})
    device.update_points({113: {"W": None}})
    assert decode_model(device, 113).W.value is None
    assert decode_model(device, 113).Hz.value == 50


@pytest.mark.parametrize("updates", [
    {999: {"W": 1}},
    {113: {"missing": 1}},
    {113: {"L": 20}},
    {113: {"ID": 1}},
    {1: {"Pad": 1}},
    {1: {"Mn": "a" * 33}},
    {1: {"Mn": "x" + "\N{LATIN SMALL LETTER A WITH DIAERESIS}" * 16}},
    {113: {"St": 65536}},
    {113: {"St": 1.5}},
    {113: {"W": float("inf")}},
    {113: {"W": float("nan")}},
    {113: {"W": True}},
    {113: {"W": "123"}},
    {113: {"W": 1e100}},
])
def test_invalid_update_is_atomic(updates):
    device = FerroampDevice()
    before = device.get_registers()
    with pytest.raises(ValueError):
        device.update_points({213: {"W": 999}, **updates})
    assert device.get_registers() == before
    assert device.models[213][0].W.value is None


@pytest.mark.parametrize("kwargs", [
    {"model_ids": ()},
    {"model_ids": (113,)},
    {"model_ids": (1, 113, 113)},
    {"model_ids": (1, 99999)},
    {"base_addr": -1},
    {"base_addr": 65535},
])
def test_invalid_model_chain_is_rejected(kwargs):
    with pytest.raises(ValueError):
        SunspecDevice(**kwargs)


def test_other_library_model_can_be_served():
    device = SunspecDevice(base_addr=0, model_ids=(1, 103))
    device.update_points({103: {"W": 1250, "W_SF": -1}})
    model = decode_model(device, 103)
    assert model.W.value == 1250
    assert model.W.cvalue == 125


def test_snapshot_is_not_mutable_by_caller():
    device = FerroampDevice()
    words = device.get_registers()
    words[0] = 0
    assert device.get_registers()[0] == 0x5375


def test_threaded_updates_publish_complete_snapshots():
    device = FerroampDevice()

    def update():
        for value in range(100):
            device.update_points({113: {"W": value, "Hz": value}})

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(update)
        for _ in range(100):
            model = decode_model(device, 113)
            assert model.W.value == model.Hz.value
        future.result()
