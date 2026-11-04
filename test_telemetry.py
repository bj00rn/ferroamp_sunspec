import pytest

from ferroamp_sunspec.device import FerroampDevice
from ferroamp_sunspec.telemetry import ehub_points


def phase(a, b, c):
    return dict(zip(("L1", "L2", "L3"), (str(a), str(b), str(c))))


def test_inverter_and_grid_measurements_map_to_separate_models():
    updates = ehub_points({
        "gridfreq": {"val": "49.95"},
        "il": phase(1, 2, 3),
        "iext": phase(4, 5, 6),
        "ul": phase(230, 231, 232),
        "pinv": phase(100, -200, 300),
        "pinvreactive": phase(10, -20, 30),
        "pext": phase(-400, 500, -600),
        "pextreactive": phase(-40, 50, -60),
        "sext": {"val": "3500"},
        "winvprodq": phase(3_600_000, 7_200_000, 10_800_000),
        "wextprodq": phase(7_200_000, 10_800_000, 14_400_000),
        "wextconsq": phase(18_000_000, 21_600_000, 25_200_000),
        "udc": {"pos": "380.30", "neg": "-379.91"},
    })
    assert updates[113] == {
        "AphA": 1, "AphB": 2, "AphC": 3, "A": 6,
        "W": -200, "VAr": 20, "WH": 6, "DCV": 760.21,
    }
    assert updates[213] == {
        "Hz": 49.95,
        "PhV": 231, "PhVphA": 230, "PhVphB": 231, "PhVphC": 232,
        "A": 15, "AphA": 4, "AphB": 5, "AphC": 6,
        "W": -500, "WphA": -400, "WphB": 500, "WphC": -600,
        "VAR": -50, "VARphA": -40, "VARphB": 50, "VARphC": -60,
        "VA": 3500,
        "TotWhExp": 9, "TotWhExpPhA": 2, "TotWhExpPhB": 3, "TotWhExpPhC": 4,
        "TotWhImp": 18, "TotWhImpPhA": 5, "TotWhImpPhB": 6, "TotWhImpPhC": 7,
    }
    device = FerroampDevice()
    device.update_points(updates)
    for model_id, points in updates.items():
        for name, value in points.items():
            assert device.models[model_id][0].points[name].value == value


def test_relevant_values_from_ferroamp_specification_example():
    updates = ehub_points({
        "gridfreq": {"val": "49.95"},
        "il": phase("2.00", "1.97", "1.97"),
        "iext": phase("3.66", "3.05", "3.53"),
        "ul": phase("239.07", "237.24", "239.06"),
        "pinv": phase("20.21", "15.18", "18.61"),
        "pinvreactive": phase("444.69", "434.94", "436.47"),
        "pext": phase("686.33", "643.69", "705.32"),
        "pextreactive": phase("169.47", "308.67", "326.25"),
        "sext": {"val": "2435.31"},
        "winvprodq": phase(1867481874316, 1743008187583, 2179580125420),
        "wextprodq": phase(939740958160, 1513371098182, 1040432778248),
        "wextconsq": phase(5654992911585, 3161182619121, 5504478918590),
    })
    assert updates[113]["A"] == pytest.approx(5.94)
    assert updates[113]["W"] == pytest.approx(-54)
    assert updates[113]["VAr"] == pytest.approx(1316.10)
    assert "VA" not in updates[113]
    assert "PhVphA" not in updates[113]
    assert "Hz" not in updates[113]
    assert updates[113]["WH"] == pytest.approx(1_608_352.8298108333)
    assert updates[213]["A"] == pytest.approx(10.24)
    assert updates[213]["W"] == pytest.approx(2035.34)
    assert updates[213]["VAR"] == pytest.approx(804.39)
    assert updates[213]["VA"] == 2435.31
    assert updates[213]["TotWhExp"] == pytest.approx(970429.1207194444)
    assert updates[213]["TotWhImp"] == pytest.approx(3977959.569248889)


def test_empty_unknown_and_partial_telemetry():
    assert ehub_points({}) == {}
    assert ehub_points({"unknown": None}) == {}
    assert ehub_points({"gridfreq": {"val": 50}}) == {213: {"Hz": 50}}


@pytest.mark.parametrize("direction", [1, -1])
def test_active_power_polarity_from_live_installation(direction):
    updates = ehub_points({
        "pinv": phase(*(direction * value for value in (-198.782, -195.968, -199.507))),
        "pext": phase(*(direction * value for value in (3886.497, 3350.092, 3488.033))),
        "pinvreactive": phase(135.482, 135.994, 138.208),
    })
    assert updates[113]["W"] == pytest.approx(direction * 594.257)
    assert updates[113]["VAr"] == pytest.approx(409.684)
    assert updates[213]["W"] == pytest.approx(direction * 10724.622)
    for name, value in zip(("WphA", "WphB", "WphC"), (3886.497, 3350.092, 3488.033)):
        assert updates[213][name] == pytest.approx(direction * value)


def test_all_documented_inverter_grid_and_load_sources_are_distinct():
    updates = ehub_points({
        "iextq": phase(10, 20, 30),
        "iextd": phase(1, 2, 3),
        "ilq": phase(40, 50, 60),
        "ild": phase(4, 5, 6),
        "pload": phase(1000, 2000, 3000),
        "pext": phase(10, 20, 30),
        "pextreactive": phase(1, 2, 3),
        "pinv": phase(40, 50, 60),
        "pinvreactive": phase(4, 5, 6),
        "sext": {"val": "15000"},
    })
    assert updates == {
        113: {"W": -150, "VAr": 15},
        213: {
            "WphA": 10, "WphB": 20, "WphC": 30, "W": 60,
            "VARphA": 1, "VARphB": 2, "VARphC": 3, "VAR": 6, "VA": 15000,
        },
    }


def test_unknown_state_pf_and_unsupported_fields_are_omitted():
    points = ehub_points({
        "state": {"val": "4096"}, "ppv": {"val": "5000"},
        "pbat": {"val": "1000"}, "soc": {"val": "50"},
        "soh": {"val": "90"}, "pext": phase(100, 200, 300),
        "sext": {"val": "1000"},
    })
    assert points == {213: {
        "WphA": 100, "WphB": 200, "WphC": 300, "W": 600, "VA": 1000,
    }}
    device = FerroampDevice()
    inverter = device.models[113][0]
    meter = device.models[213][0]
    assert inverter.St.value is None
    assert inverter.PF.value is None
    assert inverter.DCV.value is None
    assert meter.PF.value is None
    assert meter.PFphA.value is None
    assert meter.TotWhExp.value is None


def test_grid_apparent_power_uses_sext_without_estimating_phase_values():
    updates = ehub_points({
        "ul": phase(230, 230, 230), "il": phase(2, 2, 2), "iext": phase(3, 3, 3),
        "sext": {"val": "2000"}, "pinv": phase(0, 0, 0),
    })
    assert updates[213]["VA"] == 2000
    assert not any(name.startswith("VAph") for name in updates[213])
    assert updates[113]["W"] == 0
    assert "VA" not in updates[113]
    assert "PhVphA" not in updates[113]
    assert "PF" not in updates[113]
    assert "PPVphAB" not in updates[213]


def test_partial_updates_do_not_derive_apparent_power_and_retain_omitted_points():
    device = FerroampDevice()
    device.update_points(ehub_points({"ul": phase(230, 230, 230)}))
    device.update_points(ehub_points({"il": phase(1, 1, 1)}))
    assert device.models[213][0].VA.value is None
    assert device.models[113][0].VA.value is None
    device.update_points(ehub_points({"pinv": phase(100, 200, 300)}))
    device.update_points(ehub_points({"gridfreq": {"val": "50"}}))
    assert device.models[113][0].W.value == -600
    assert device.models[113][0].Hz.value is None
    assert device.models[213][0].Hz.value == 50
    assert device.models[213][0].PhV.value == 230


def test_large_counters_are_summed_as_integers_before_conversion():
    value = 2 ** 64 - 1
    updates = ehub_points({"winvprodq": phase(value, value, value)})
    assert updates[113]["WH"] == (value * 3) / 3_600_000


@pytest.mark.parametrize("value", [
    None, [], {}, {"val": "invalid"}, {"val": True}, {"val": "NaN"}, {"val": "inf"},
    {"val": 10 ** 400},
])
def test_invalid_scalar_telemetry(value):
    with pytest.raises(ValueError):
        ehub_points({"gridfreq": value})


@pytest.mark.parametrize("value", [
    "-1", "1.5", "1e6", "NaN", str(2 ** 64), 1.0, -1, True, None, " 1", "\u0661",
])
@pytest.mark.parametrize("key", ["winvprodq", "wextprodq", "wextconsq"])
def test_energy_counter_validation(key, value):
    with pytest.raises(ValueError, match=key):
        ehub_points({key: {"L1": value, "L2": "0", "L3": "0"}})


@pytest.mark.parametrize("key", [
    "il", "iext", "ul", "pinv", "pinvreactive", "pext", "pextreactive",
    "winvprodq", "wextprodq", "wextconsq",
])
def test_incomplete_phase_data_is_rejected_before_publication(key):
    device = FerroampDevice()
    before = device.get_registers()
    with pytest.raises(ValueError):
        device.update_points(ehub_points({
            "gridfreq": {"val": "50"}, key: {"L1": "230", "L2": "230"},
        }))
    assert device.get_registers() == before


@pytest.mark.parametrize("data", [
    {"il": phase(-1, 2, 3)}, {"iext": phase(1, -2, 3)},
    {"ul": phase(230, 230, -230)}, {"sext": {"val": "-1"}},
    {"udc": {"pos": "-380", "neg": "-380"}}, {"udc": {"pos": "380", "neg": "380"}},
    {"udc": {"val": "760"}},
])
def test_invalid_rms_apparent_or_dc_rail_values(data):
    with pytest.raises(ValueError):
        ehub_points(data)
