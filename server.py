"""Modbus TCP transport for a pysunspec2-backed device."""

import asyncio
import logging

from pymodbus.datastore import ModbusServerContext
from pymodbus.datastore.context import ModbusBaseSlaveContext
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.server import ModbusTcpServer

from device import SunspecDevice

log = logging.getLogger(__name__)


class SunSpecDataStore(ModbusBaseSlaveContext):
    """Read-only holding registers using zero-based Modbus wire addresses."""

    def __init__(self, device: SunspecDevice):
        self.device = device
        self.length = len(device.get_registers())

    def validate(self, fc_as_hex, address, count=1):
        return (
            fc_as_hex == 3
            and count > 0
            and self.device.base_addr <= address
            and address + count <= self.device.base_addr + self.length
        )

    def getValues(self, fc_as_hex, address, count=1):
        if not self.validate(fc_as_hex, address, count):
            raise ValueError("Invalid SunSpec holding-register read")
        offset = address - self.device.base_addr
        return self.device.get_registers()[offset:offset + count]

    def setValues(self, fc_as_hex, address, values):
        raise ValueError("SunSpec telemetry registers are read-only")


class SunspecServer:
    def __init__(
        self,
        device: SunspecDevice,
        port: int = 502,
        host: str = "0.0.0.0",
        unit_id: int = 1,
    ):
        if not 0 <= port <= 65535:
            raise ValueError("port must be in 0..65535")
        if not 1 <= unit_id <= 247:
            raise ValueError("unit_id must be in 1..247")
        self.device = device
        self.host = host
        self.port = port
        self.unit_id = unit_id
        self.store = SunSpecDataStore(device)
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
        server = ModbusTcpServer(
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
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    device = FerroampDevice(base_addr=args.base_addr, unit_id=args.unit_id)
    await SunspecServer(device, port=args.port, host=args.host, unit_id=args.unit_id).run_forever()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
