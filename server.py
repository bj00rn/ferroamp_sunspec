"""Modbus TCP transport for a pysunspec2-backed device."""

import asyncio
from collections.abc import Set
from copy import copy
import logging
import struct

from pymodbus.datastore import ModbusServerContext
from pymodbus.datastore.context import ModbusBaseSlaveContext
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.server import ModbusTcpServer
from pymodbus.server.requesthandler import ServerRequestHandler

from device import SunspecDevice
from configuration import parse_configuration

log = logging.getLogger(__name__)


class LoggingRequestHandler(ServerRequestHandler):
    def callback_connected(self) -> None:
        super().callback_connected()
        self.peer = self.transport.get_extra_info("peername")
        log.info("Modbus TCP client connected peer=%s", self.peer)

    def callback_disconnected(self, call_exc: Exception | None) -> None:
        super().callback_disconnected(call_exc)
        log.info("Modbus TCP client disconnected peer=%s reason=%s", self.peer, call_exc)


class LoggingModbusTcpServer(ModbusTcpServer):
    def callback_new_connection(self):
        return LoggingRequestHandler(
            self, self.trace_packet, self.trace_pdu, self.trace_connect,
        )


class SunSpecDataStore(ModbusBaseSlaveContext):
    """Read-only holding registers using zero-based Modbus wire addresses."""

    def __init__(
        self, device: SunspecDevice, unit_id: int, trace: bool = False,
        stale_points: Set[tuple[int, str]] | None = None,
    ):
        self.device = device
        self.unit_id = unit_id
        self.trace = trace
        self.stale_points = stale_points
        self.length = len(device.get_registers())

    def validate(self, fc_as_hex, address, count=1):
        accepted = (
            fc_as_hex == 3
            and count > 0
            and self.device.base_addr <= address
            and address + count <= self.device.base_addr + self.length
        )
        if self.trace:
            log.info(
                "Modbus request unit=%s function=%s address=%s count=%s accepted=%s",
                self.unit_id, fc_as_hex, address, count, accepted,
            )
        return accepted

    def getValues(self, fc_as_hex, address, count=1):
        if not self.validate(fc_as_hex, address, count):
            raise ValueError("Invalid SunSpec holding-register read")
        offset = address - self.device.base_addr
        snapshot = self.device.get_registers()
        registers = snapshot[offset:offset + count]
        if self.stale_points:
            stale = []
            for model_id, name in sorted(self.stale_points):
                model = self.device.models[model_id][0]
                point = model.points[name]
                start = model.model_addr + point.offset
                if start < address + count and address < start + point.len:
                    stale.append(f"{model_id}.{name}")
            if stale:
                log.warning(
                    "Modbus read of stale telemetry unit=%s function=%s address=%s count=%s points=%s",
                    self.unit_id, fc_as_hex, address, count, ", ".join(stale),
                )
        if self.trace or log.isEnabledFor(logging.DEBUG):
            points = {}
            unsupported = []
            for model in self.device.sunspec.model_list:
                for name, point in model.points.items():
                    start = model.model_addr + point.offset - address
                    if start < count and start + point.len > 0:
                        decoded = copy(point)
                        point_offset = offset + start
                        decoded.set_mb(b"".join(
                            struct.pack(">H", word)
                            for word in snapshot[point_offset:point_offset + point.len]
                        ))
                        if 0 <= start and start + point.len <= count:
                            points[f"{model.model_id}.{name}"] = decoded.value
                        key = (model.model_id, name)
                        if (
                            decoded.value is None
                            and (self.stale_points is None or key not in self.stale_points)
                        ):
                            unsupported.append(f"{model.model_id}.{name}")
            if unsupported:
                log.debug(
                    "Modbus read of unavailable non-stale points "
                    "unit=%s function=%s address=%s count=%s points=%s",
                    self.unit_id, fc_as_hex, address, count, ", ".join(unsupported),
                )
            if self.trace:
                log.info(
                    "Modbus response unit=%s function=%s address=%s count=%s registers=%s points=%s",
                    self.unit_id, fc_as_hex, address, count, registers, points,
                )
        return registers

    def setValues(self, fc_as_hex, address, values):
        raise ValueError("SunSpec telemetry registers are read-only")


class SunspecServer:
    def __init__(
        self,
        device: SunspecDevice,
        port: int = 502,
        host: str = "0.0.0.0",
        unit_id: int = 1,
        trace_modbus: bool = False,
        stale_points: Set[tuple[int, str]] | None = None,
    ):
        if not 0 <= port <= 65535:
            raise ValueError("port must be in 0..65535")
        if not 1 <= unit_id <= 247:
            raise ValueError("unit_id must be in 1..247")
        self.device = device
        self.host = host
        self.port = port
        self.unit_id = unit_id
        self.store = SunSpecDataStore(
            device, unit_id=unit_id, trace=trace_modbus, stale_points=stale_points,
        )
        self.context = ModbusServerContext(slaves={unit_id: self.store}, single=False)
        common = device.models[1][0]
        self.identity = ModbusDeviceIdentification()
        self.identity.VendorName = common.Mn.value or "SunSpec"
        self.identity.ModelName = common.Md.value or "SunSpec device"
        self.identity.MajorMinorRevision = common.Vr.value or "1"
        self._server: ModbusTcpServer | None = None

    async def start(self) -> None:
        """Bind the socket, raising on failure rather than pretending to start."""
        if self._server is not None:
            raise RuntimeError("SunSpec server is already started")
        server = LoggingModbusTcpServer(
            context=self.context,
            identity=self.identity,
            address=(self.host, self.port),
        )
        started = False
        try:
            await server.serve_forever(background=True)
            if not server.is_active():
                raise OSError(f"Cannot bind Modbus TCP server to {self.host}:{self.port}")
            started = True
        finally:
            if not started:
                await server.shutdown()
        self._server = server
        log.info("SunSpec Modbus TCP listening on %s:%s, unit %s, base %s",
                 self.host, self.port, self.unit_id, self.device.base_addr)

    async def stop(self) -> None:
        if self._server is not None:
            await self._server.shutdown()
            self._server = None

    async def run_forever(self) -> None:
        await self.start()
        server = self._server
        assert server is not None
        try:
            await server.serving
        finally:
            await self.stop()


async def main():
    import argparse
    from device import FerroampDevice

    parser = argparse.ArgumentParser(description="Run a standalone SunSpec Modbus TCP server.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=502)
    parser.add_argument("--base-addr", type=int, default=40000)
    parser.add_argument("--unit-id", type=int, default=1)
    parser.add_argument(
        "--log-level", type=str.upper, default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
        help="logging threshold (default: INFO)",
    )
    parser.add_argument(
        "--trace-modbus", action="store_true",
        help="log each Modbus request's unit, function, address, count, and validation result",
    )
    args = parse_configuration(parser)
    logging.basicConfig(level=args.log_level)
    logging.getLogger().setLevel(args.log_level)
    device = FerroampDevice(base_addr=args.base_addr, unit_id=args.unit_id)
    await SunspecServer(
        device, port=args.port, host=args.host, unit_id=args.unit_id,
        trace_modbus=args.trace_modbus,
    ).run_forever()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
