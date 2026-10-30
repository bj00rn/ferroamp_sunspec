import asyncio
from pathlib import Path
import socket
import struct
import subprocess
import sys

import pytest
from pymodbus.client import ModbusTcpClient
from sunspec2.modbus.client import SunSpecModbusClientDeviceTCP

from device import FerroampDevice
from server import SunspecServer


def bound_port(server):
    return server._server.transport.sockets[0].getsockname()[1]


@pytest.mark.parametrize("base_addr,unit_id", [(40000, 1), (0, 7), (50000, 1)])
def test_real_sunspec_client_discovers_and_reads(base_addr, unit_id):
    async def scenario():
        device = FerroampDevice(base_addr=base_addr, unit_id=unit_id)
        device.update_points({113: {"W": 1234.5, "Hz": 50}, 214: {"W": -500}})
        server = SunspecServer(device, host="127.0.0.1", port=0, unit_id=unit_id)
        await server.start()

        def read():
            client = SunSpecModbusClientDeviceTCP(
                ipaddr="127.0.0.1", ipport=bound_port(server),
                slave_id=unit_id, timeout=1,
            )
            client.base_addr_list = [base_addr]
            try:
                client.scan()
                assert [model.model_id for model in client.model_list] == [1, 113, 214]
                assert all(not model.error_info for model in client.model_list)
                assert client.models[1][0].Mn.value == "Ferroamp"
                assert client.models[1][0].DA.value == unit_id
                assert client.models[113][0].W.value == 1234.5
                assert client.models[113][0].Hz.value == 50
                assert client.models[113][0].TmpCab.value is None
                assert client.models[214][0].W.value == -500
                assert client.models[214][0].TotWhImp.value is None
                device.update_points({113: {"W": 7654.5}, 214: {"TotWhImp": 555}})
                client.models[113][0].read()
                client.models[214][0].read()
                assert client.models[113][0].W.value == 7654.5
                assert client.models[113][0].Hz.value == 50
                assert client.models[214][0].TotWhImp.value == 555
            finally:
                client.close()

        try:
            await asyncio.wait_for(asyncio.to_thread(read), timeout=10)
        finally:
            await server.stop()
        assert server._server is None

    asyncio.run(scenario())


def test_wire_addressing_ranges_and_read_only_registers():
    async def scenario():
        device = FerroampDevice()
        server = SunspecServer(device, host="127.0.0.1", port=0)
        await server.start()

        def requests():
            client = ModbusTcpClient("127.0.0.1", port=bound_port(server), timeout=1)
            try:
                assert client.connect()
                assert client.read_holding_registers(40000, count=2, slave=1).registers == [0x5375, 0x6E53]
                end = 40000 + len(device.get_registers()) - 2
                assert client.read_holding_registers(end, count=2, slave=1).registers == [65535, 0]
                for address, count in ((39999, 1), (end + 1, 2)):
                    assert client.read_holding_registers(address, count=count, slave=1).isError()
                # pymodbus 3.8 emits an undecodable function code for a missing
                # unit. Check its gateway exception on the wire instead.
                with socket.create_connection(("127.0.0.1", bound_port(server)), timeout=1) as other:
                    other.sendall(struct.pack(">HHHBBHH", 1, 0, 6, 2, 3, 40000, 1))
                    response = b""
                    while len(response) < 9:
                        chunk = other.recv(9 - len(response))
                        assert chunk
                        response += chunk
                    assert response[6] == 2
                    assert response[7] & 0x80
                    assert response[8] == 11
                assert client.read_input_registers(40000, count=1, slave=1).isError()
                assert client.write_register(40000, 0, slave=1).isError()
                assert client.write_registers(40000, [0, 0], slave=1).isError()
                assert client.read_holding_registers(40000, count=2, slave=1).registers == [0x5375, 0x6E53]
            finally:
                client.close()

        try:
            await asyncio.wait_for(asyncio.to_thread(requests), timeout=10)
        finally:
            await server.stop()

    asyncio.run(scenario())


def test_start_reports_bind_failure():
    async def scenario():
        with socket.socket() as occupied:
            occupied.bind(("127.0.0.1", 0))
            occupied.listen()
            server = SunspecServer(
                FerroampDevice(), host="127.0.0.1", port=occupied.getsockname()[1],
            )
            with pytest.raises(OSError, match="Cannot bind"):
                await server.start()
            assert server._server is None

    asyncio.run(scenario())


def test_server_cancellation_closes_socket():
    async def scenario():
        server = SunspecServer(FerroampDevice(), host="127.0.0.1", port=0)
        task = asyncio.create_task(server.run_forever())
        try:
            async def ready():
                while server._server is None:
                    await asyncio.sleep(0.01)
            await asyncio.wait_for(ready(), timeout=2)
            port = bound_port(server)
        finally:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        assert server._server is None
        with pytest.raises(OSError):
            await asyncio.open_connection("127.0.0.1", port)

    asyncio.run(scenario())


def test_core_does_not_import_mqtt():
    result = subprocess.run(
        [sys.executable, "-c",
         "import sys; import server; from device import FerroampDevice; "
         "server.SunspecServer(FerroampDevice()); "
         "assert 'mqtt' not in sys.modules; assert 'paho.mqtt.client' not in sys.modules"],
        cwd=Path(__file__).parent, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr
