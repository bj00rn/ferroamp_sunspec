import asyncio
import logging
from pymodbus.datastore import ModbusServerContext, ModbusSlaveContext
from pymodbus.datastore.store import ModbusSequentialDataBlock
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.server import StartAsyncTcpServer
from device import FerroampDevice

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


class SunspecServer:
    """
    A class to represent a SunSpec server that combines Common Data Block and Model 111 Data Block.
    """

    def __init__(self, device, port=502, base_addr=40001):
        """
        Initialize the SunspecServer with a device.

        Args:
            device (FerroampDevice): The Ferroamp device to be used.
        """
        self.device = device
        self.base_addr = base_addr
        self.port = port

        # Set up device identification
        self.identity = ModbusDeviceIdentification()
        self.identity.VendorName = "SunSpec"
        self.identity.ProductCode = "Three-Phase Inverter"
        self.identity.ModelName = "SunSpec Inverter Model 111"
        self.identity.MajorMinorRevision = "1.0"

        # Create a Modbus datastore
        self.data_block = ModbusSequentialDataBlock(self.base_addr, device.get_registers())
        self.store = ModbusSlaveContext(di=None, co=None, hr=self.data_block, ir=None)
        self.context = ModbusServerContext(slaves=self.store, single=True)

    def run_forever(self):
        """
        Start the Modbus TCP server.

        Args:
            port (int): The port number to bind the server.
        """
        log.info(f"Starting Modbus TCP server on port {self.port}...")
        return StartAsyncTcpServer(
            context=self.context,
            identity=self.identity,
            address=("0.0.0.0", self.port),
        )

    def update_data(self):
        """
        Update the data block with the latest values from the Ferroamp device.
        """
        log.info("Updating data block with latest values from Ferroamp device...")
        self.data_block.setValues(self.base_addr, self.device.get_registers())
