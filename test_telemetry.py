import pytest

from device import FerroampDevice
from telemetry import inverter_points


def test_existing_mapping_is_preserved_outside_models():
    updates = inverter_points({
        "gridfreq": {"val": "50"},
        "iextq": {"L1": "1", "L2": "2", "L3": "3"},
        "ul": {"L1": "230", "L2": "231", "L3": "232"},
        "pload": {"L1": "100", "L2": "200", "L3": "300"},
        "sext": {"val": "650"},
        "winvprodq": {"L1": "1000", "L2": "2000", "L3": "3000"},
        "unrelated": {"val": "ignored"},
    })
    device = FerroampDevice()
    device.update_points(updates)
    assert updates == {113: {
        "Hz": 50, "A": 6, "AphA": 1, "AphB": 2, "AphC": 3,
        "PhVphA": 230, "PhVphB": 231, "PhVphC": 232,
        "W": 600, "VA": 650, "WH": 6000,
    }}
    assert device.models[214][0].W.value is None


def test_empty_and_partial_telemetry():
    assert inverter_points({}) == {113: {}}
    assert inverter_points({"gridfreq": {"val": 50}}) == {113: {"Hz": 50}}


@pytest.mark.parametrize("value", [
    None, [], {}, {"val": "invalid"}, {"val": True}, {"val": "NaN"}, {"val": "inf"},
    {"val": 10 ** 400},
])
def test_invalid_scalar_telemetry(value):
    with pytest.raises(ValueError):
        inverter_points({"gridfreq": value})


def test_incomplete_phase_data_is_rejected_before_publication():
    device = FerroampDevice()
    before = device.get_registers()
    with pytest.raises(ValueError):
        device.update_points(inverter_points({
            "gridfreq": {"val": "50"},
            "ul": {"L1": "230", "L2": "230"},
        }))
    assert device.get_registers() == before
