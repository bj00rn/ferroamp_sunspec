"""Ferroamp External API revision E, section 4.1.2 -> SunSpec 113/213."""

from collections.abc import Mapping
import math

from .device import PointValue

PHASES = ("L1", "L2", "L3")
MILLIJOULES_PER_WH = 3_600_000


def ehub_points(data: Mapping[str, object]) -> dict[int, dict[str, PointValue]]:
    """Map EnergyHub inverter and external-grid telemetry to separate models."""
    inverter: dict[str, PointValue] = {}
    meter: dict[str, PointValue] = {}

    def number(key: str, field: str, *, counter: bool = False) -> int | float:
        values = data[key]
        if not isinstance(values, Mapping):
            raise ValueError(f"{key} must be an object")
        value = values.get(field)
        if isinstance(value, bool) or not isinstance(value, (str, int, float)):
            raise ValueError(f"{key}.{field} must be numeric")
        if counter:
            if isinstance(value, str):
                if not value.isascii() or not value.isdecimal():
                    raise ValueError(f"{key}.{field} must be a uint64 counter")
                value = int(value)
            if not isinstance(value, int) or not 0 <= value < 2 ** 64:
                raise ValueError(f"{key}.{field} must be a uint64 counter")
            return value
        try:
            result = float(value)
        except (ValueError, OverflowError) as exc:
            raise ValueError(f"{key}.{field} must be numeric") from exc
        if not math.isfinite(result):
            raise ValueError(f"{key}.{field} must be finite")
        return result

    def phases(key: str, *, counter: bool = False) -> list[int | float]:
        return [number(key, phase, counter=counter) for phase in PHASES]

    def nonnegative(key: str, values: list[int | float]) -> None:
        if any(value < 0 for value in values):
            raise ValueError(f"{key} must contain nonnegative RMS measurements")

    if "gridfreq" in data:
        meter["Hz"] = number("gridfreq", "val")

    if "ul" in data:
        voltage = phases("ul")
        nonnegative("ul", voltage)
        meter.update(zip(("PhVphA", "PhVphB", "PhVphC"), voltage))
        meter["PhV"] = sum(voltage) / 3

    for key, points in (("il", inverter), ("iext", meter)):
        if key in data:
            current = phases(key)
            nonnegative(key, current)
            points.update(zip(("AphA", "AphB", "AphC"), current))
            points["A"] = sum(current)

    for key, points, total, names in (
        ("pinv", inverter, "W", ()),
        ("pinvreactive", inverter, "VAr", ()),
        ("pext", meter, "W", ("WphA", "WphB", "WphC")),
        ("pextreactive", meter, "VAR", ("VARphA", "VARphB", "VARphC")),
    ):
        if key in data:
            power = phases(key)
            if key == "pinv":
                power = [-value for value in power]
            points.update(zip(names, power))
            points[total] = sum(power)

    if "sext" in data:
        apparent = number("sext", "val")
        nonnegative("sext", [apparent])
        meter["VA"] = apparent

    if "winvprodq" in data:
        inverter["WH"] = sum(phases("winvprodq", counter=True)) / MILLIJOULES_PER_WH
    for key, total, names in (
        ("wextprodq", "TotWhExp", ("TotWhExpPhA", "TotWhExpPhB", "TotWhExpPhC")),
        ("wextconsq", "TotWhImp", ("TotWhImpPhA", "TotWhImpPhB", "TotWhImpPhC")),
    ):
        if key in data:
            energy = phases(key, counter=True)
            meter.update(zip(names, (value / MILLIJOULES_PER_WH for value in energy)))
            meter[total] = sum(energy) / MILLIJOULES_PER_WH

    if "udc" in data:
        positive = number("udc", "pos")
        negative = number("udc", "neg")
        if positive < 0 or negative > 0:
            raise ValueError("udc rails must have pos >= 0 and neg <= 0")
        inverter["DCV"] = positive - negative

    return {model_id: points for model_id, points in ((113, inverter), (213, meter)) if points}
