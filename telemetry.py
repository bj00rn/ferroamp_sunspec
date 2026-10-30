"""Legacy Ferroamp ExtApi mappings, kept outside the SunSpec implementation."""

from collections.abc import Mapping
import math

from device import PointValue


def inverter_points(data: Mapping[str, object]) -> dict[int, dict[str, PointValue]]:
    """Convert a partial ExtApi payload into a transport-neutral point update.

    These preserve the experiment's existing mappings. The physical meanings of
    iextq, pload, sext and the energy units need verification against the device.
    """
    points: dict[str, PointValue] = {}

    def number(key: str, field: str) -> float:
        values = data[key]
        if not isinstance(values, Mapping):
            raise ValueError(f"{key} must be an object")
        value = values.get(field)
        if isinstance(value, bool) or not isinstance(value, (str, int, float)):
            raise ValueError(f"{key}.{field} must be numeric")
        try:
            result = float(value)
        except (ValueError, OverflowError) as exc:
            raise ValueError(f"{key}.{field} must be numeric") from exc
        if not math.isfinite(result):
            raise ValueError(f"{key}.{field} must be finite")
        return result

    for key, name in (("gridfreq", "Hz"), ("sext", "VA")):
        if key in data:
            points[name] = number(key, "val")
    for key, names, total in (
        ("iextq", ("AphA", "AphB", "AphC"), "A"),
        ("ul", ("PhVphA", "PhVphB", "PhVphC"), None),
        ("pload", (), "W"),
        ("winvprodq", (), "WH"),
    ):
        if key in data:
            phases = [number(key, phase) for phase in ("L1", "L2", "L3")]
            points.update(zip(names, phases))
            if total is not None:
                points[total] = sum(phases)
    return {113: points}
