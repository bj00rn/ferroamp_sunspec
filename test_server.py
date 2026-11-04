import asyncio
import logging
from pathlib import Path
import socket
import struct
import subprocess
import sys

import pytest
from pymodbus.client import ModbusTcpClient
from sunspec2.modbus.client import SunSpecModbusClientDeviceTCP

from ferroamp_sunspec.device import FerroampDevice
from ferroamp_sunspec.server import SunspecServer
from ferroamp_sunspec.telemetry import ehub_points


def bound_port(server):
    return server._server.transport.sockets[0].getsockname()[1]


@pytest.mark.parametrize("base_addr,unit_id", [(40000, 1), (0, 7), (50000, 1)])
def test_real_sunspec_client_discovers_and_reads(base_addr, unit_id):
    async def scenario():
        device = FerroampDevice(base_addr=base_addr, unit_id=unit_id)
        device.update_points({113: {"W": 1234.5, "Hz": 50}, 213: {"W": -500}})
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
                assert [model.model_id for model in client.model_list] == [1, 113, 213]
                assert all(not model.error_info for model in client.model_list)
                assert client.models[1][0].Mn.value == "Ferroamp"
                assert client.models[1][0].DA.value == unit_id
                assert client.models[113][0].W.value == 1234.5
                assert client.models[113][0].Hz.value == 50
                assert client.models[113][0].TmpCab.value is None
                assert client.models[213][0].W.value == -500
                assert client.models[213][0].TotWhImp.value is None
                device.update_points({113: {"W": 7654.5}, 213: {"TotWhImp": 555}})
                client.models[113][0].read()
                client.models[213][0].read()
                assert client.models[113][0].W.value == 7654.5
                assert client.models[113][0].Hz.value == 50
                assert client.models[213][0].TotWhImp.value == 555
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


def test_modbus_request_tracing_is_opt_in(caplog):
    async def scenario():
        quiet_server = SunspecServer(FerroampDevice(), host="127.0.0.1", port=0)
        with caplog.at_level(logging.INFO, logger="ferroamp_sunspec.server"):
            assert quiet_server.store.validate(3, 40000, 2)
            quiet_server.store.getValues(3, 40000, 2)
            assert "Modbus request" not in caplog.text
            assert "Modbus response" not in caplog.text

            device = FerroampDevice()
            device.update_points({213: {"W": -10547.934}})
            server = SunspecServer(
                device, host="127.0.0.1", port=0, unit_id=7,
                trace_modbus=True,
            )
            await server.start()

            def read():
                client = ModbusTcpClient("127.0.0.1", port=bound_port(server), timeout=1)
                try:
                    assert client.connect()
                    response = client.read_holding_registers(40000, count=2, slave=7)
                    assert not response.isError()
                    response = client.read_holding_registers(40160, count=2, slave=7)
                    assert not response.isError()
                finally:
                    client.close()

            try:
                await asyncio.wait_for(asyncio.to_thread(read), timeout=5)
            finally:
                await server.stop()

        assert "unit=7 function=3 address=40000 count=2 accepted=True" in caplog.text
        assert "Modbus response unit=7 function=3 address=40160 count=2 registers=" in caplog.text
        assert "'213.W': -10547.93359375" in caplog.text

    asyncio.run(scenario())


def test_client_connection_is_logged_without_request_tracing(caplog):
    async def scenario():
        server = SunspecServer(FerroampDevice(), host="127.0.0.1", port=0)
        with caplog.at_level(logging.INFO, logger="ferroamp_sunspec.server"):
            await server.start()
            try:
                reader, writer = await asyncio.open_connection("127.0.0.1", bound_port(server))
                peer = writer.get_extra_info("sockname")
                try:
                    await asyncio.sleep(0)
                    assert f"Modbus TCP client connected peer={peer}" in caplog.text
                finally:
                    writer.close()
                    await writer.wait_closed()
                    async def disconnected():
                        while "Modbus TCP client disconnected" not in caplog.text:
                            await asyncio.sleep(0)
                    await asyncio.wait_for(disconnected(), timeout=1)
                    assert f"Modbus TCP client disconnected peer={peer}" in caplog.text
            finally:
                await server.stop()
        assert "Modbus request" not in caplog.text

    asyncio.run(scenario())


def test_unavailable_point_reads_log_debug_without_stale_warning(caplog):
    device = FerroampDevice()
    server = SunspecServer(device)
    model = device.models[113][0]
    address = model.model_addr + model.DCW.offset
    with caplog.at_level(logging.DEBUG, logger="ferroamp_sunspec.server"):
        server.store.getValues(3, address + 1, 1)
    assert "unavailable non-stale points" in caplog.text
    assert "points=113.DCW" in caplog.text
    assert all(record.levelno == logging.DEBUG for record in caplog.records)
    caplog.clear()
    device.update_points({113: {"DCW": 500}})
    with caplog.at_level(logging.DEBUG, logger="ferroamp_sunspec.server"):
        server.store.getValues(3, address, 2)
    assert not caplog.records


def test_energyhub_mapping_round_trips_through_sunspec_tcp():
    async def scenario():
        device = FerroampDevice()
        device.update_points(ehub_points({
            "gridfreq": {"val": "49.95"},
            "ul": {"L1": "230", "L2": "231", "L3": "232"},
            "il": {"L1": "1", "L2": "2", "L3": "3"},
            "iext": {"L1": "4", "L2": "5", "L3": "6"},
            "pinv": {"L1": "-100", "L2": "200", "L3": "-300"},
            "pinvreactive": {"L1": "10", "L2": "20", "L3": "30"},
            "pext": {"L1": "400", "L2": "-500", "L3": "600"},
            "pextreactive": {"L1": "-40", "L2": "-50", "L3": "-60"},
            "sext": {"val": "3500"},
            "winvprodq": {"L1": "3600000", "L2": "7200000", "L3": "10800000"},
            "wextprodq": {"L1": "7200000", "L2": "10800000", "L3": "14400000"},
            "wextconsq": {"L1": "18000000", "L2": "21600000", "L3": "25200000"},
            "udc": {"pos": "380.30", "neg": "-379.91"},
        }))
        server = SunspecServer(device, host="127.0.0.1", port=0)
        await server.start()

        def read():
            client = SunSpecModbusClientDeviceTCP(
                ipaddr="127.0.0.1", ipport=bound_port(server), timeout=1,
            )
            try:
                client.scan()
                inverter = client.models[113][0]
                meter = client.models[213][0]
                for name, value in {
                    "W": 200, "VAr": 60, "A": 6, "WH": 6,
                    "AphC": 3,
                }.items():
                    assert inverter.points[name].value == pytest.approx(value)
                assert inverter.Hz.value is None
                assert inverter.VA.value is None
                assert inverter.PhVphB.value is None
                for name, value in {
                    "W": 500, "WphB": -500, "VAR": -150, "VARphC": -60,
                    "A": 15, "AphC": 6, "VA": 3500,
                    "PhV": 231, "PhVphC": 232, "Hz": 49.95,
                    "TotWhExp": 9, "TotWhExpPhB": 3,
                    "TotWhImp": 18, "TotWhImpPhC": 7,
                }.items():
                    assert meter.points[name].value == pytest.approx(value)
                assert meter.VAphA.value is None
                assert inverter.St.value is None
                assert inverter.DCW.value is None
                assert meter.PPV.value is None
                assert meter.PF.value is None
            finally:
                client.close()

        try:
            await asyncio.wait_for(asyncio.to_thread(read), timeout=10)
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
         "import sys; from ferroamp_sunspec import server; "
         "from ferroamp_sunspec.device import FerroampDevice; "
         "server.SunspecServer(FerroampDevice()); "
         "assert 'ferroamp_sunspec.mqtt' not in sys.modules; "
         "assert 'aiomqtt' not in sys.modules; assert 'paho.mqtt.client' not in sys.modules"],
        cwd=Path(__file__).parent, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr
