"""Transport-independent SunSpec devices backed by pysunspec2."""

from collections.abc import Mapping, Sequence
from copy import copy
import math
import struct
from threading import RLock

from sunspec2 import device, mb

PointValue = str | int | float | None


class SunspecDevice:
    """A fixed model chain with atomically published register snapshots.

    ``models`` exposes pysunspec2's model lookup (by ID or group name).
    Use ``update_points`` to publish changes, rather than mutating those models.
    """

    def __init__(
        self,
        base_addr: int = mb.SUNS_BASE_ADDR_DEFAULT,
        model_ids: Sequence[int] = (1, 113, 214),
    ):
        if not model_ids or model_ids[0] != 1:
            raise ValueError("The Common model (1) must be first")
        if len(set(model_ids)) != len(model_ids):
            raise ValueError("Model IDs must be unique")
        if not isinstance(base_addr, int) or not 0 <= base_addr <= 65535:
            raise ValueError("base_addr must be a Modbus wire address (0..65535)")

        self.base_addr = base_addr
        self.sunspec = device.Device()
        self._lock = RLock()
        address = base_addr + mb.SUNS_SUNS_LEN
        for model_id in model_ids:
            model = device.Model(model_id=model_id, model_addr=address)
            if model.error_info:
                raise ValueError(f"Cannot load SunSpec model {model_id}: {model.error_info}")
            self.sunspec.add_model(model)
            address += model.len
        if address + 2 > 65536:
            raise ValueError("SunSpec model chain exceeds the Modbus address space")

        data = b"SunS" + self.sunspec.get_mb() + struct.pack(">HH", mb.SUNS_END_MODEL_ID, 0)
        self._registers = tuple(word[0] for word in struct.iter_unpack(">H", data))

    @property
    def models(self) -> dict[int | str, list[device.Model]]:
        return self.sunspec.models

    def get_registers(self) -> list[int]:
        """Return a complete snapshot, including signature and end marker."""
        with self._lock:
            return list(self._registers)

    def update_points(self, updates: Mapping[int, Mapping[str, PointValue]]) -> None:
        """Publish raw SunSpec point values; None means not implemented.

        Omitted points retain their previous value. All values are checked and
        encoded by the library before any model or register value is changed.
        """
        with self._lock:
            registers = list(self._registers)
            changes: list[tuple[device.Point, PointValue]] = []
            for model_id, values in updates.items():
                models = self.models.get(model_id)
                if models is None:
                    raise ValueError(f"Unknown SunSpec model: {model_id}")
                model = models[0]
                for name, value in values.items():
                    if name in ("ID", "L", "Pad"):
                        raise ValueError(f"Cannot update structural point {model_id}.{name}")
                    point = model.points.get(name)
                    if point is None:
                        raise ValueError(f"Unknown SunSpec point: {model_id}.{name}")
                    if value is not None:
                        if point.pdef["type"] == "string":
                            if not isinstance(value, str) or len(value.encode("utf-8")) > point.len * 2:
                                raise ValueError(f"Invalid string for {model_id}.{name}")
                        elif (
                            isinstance(value, bool)
                            or not isinstance(value, (int, float))
                            or (isinstance(value, float) and not math.isfinite(value))
                        ):
                            raise ValueError(f"Invalid numeric value for {model_id}.{name}: {value!r}")

                    candidate = copy(point)
                    candidate.value = value
                    try:
                        encoded = candidate.get_mb()
                    except device.ModelError as exc:
                        raise ValueError(f"Invalid value for {model_id}.{name}: {exc}") from exc
                    words = [word[0] for word in struct.iter_unpack(">H", encoded)]
                    if len(words) != point.len:
                        raise ValueError(f"Invalid encoded length for {model_id}.{name}")
                    offset = model.model_addr - self.base_addr + point.offset
                    registers[offset:offset + point.len] = words
                    changes.append((point, value))

            for point, value in changes:
                point.value = value
            self._registers = tuple(registers)


class FerroampDevice(SunspecDevice):
    """Ferroamp profile; no dependency on the source of its measurements."""

    def __init__(self, base_addr: int = mb.SUNS_BASE_ADDR_DEFAULT, unit_id: int = 1):
        if not 1 <= unit_id <= 247:
            raise ValueError("unit_id must be in 1..247")
        super().__init__(base_addr=base_addr)
        self.update_points({
            1: {
                "Mn": "Ferroamp",
                "Md": "Energyhub 14",
                "Opt": "",
                "Vr": "1",
                "SN": "123456789",
                "DA": unit_id,
            },
        })
