import argparse
import time
from sunspec2.modbus.client import SunSpecModbusClientDeviceTCP, SunSpecModbusClientModel
from sunspec2.modbus.modbus import ModbusClientTimeout


def read_sunspec_inverter(ip, port=502, retries=3, delay=2):
    """
    Connect to a SunSpec inverter using SunSpecModbusClientDeviceTCP and read data.
    Retries the connection in case of failure.
    """
    attempt = 0
    while attempt < retries:
        try:
            # Create a SunSpec Modbus TCP client device
            device = SunSpecModbusClientDeviceTCP(ipaddr=ip, ipport=port, slave_id=1)
            # Scan for SunSpec models
            device.base_addr_list = [40000]
            device.scan()
            if not device.models:
                print("No SunSpec models found on the device.")
                return

            # Access the Common Block (Model 1)
            common_model: "SunSpecModbusClientModel" = device.models.get(1)[0]
            if not common_model:
                print("SunSpec Common Block (Model 1) not found.")
                return

            manufacturer = common_model.get_dict().get("Mn", None)  # Manufacturer
            if not manufacturer:
                print("Device is not SunSpec-compliant.")
                return
            print(f"SunSpec Manufacturer: {manufacturer}")

            # Access the Inverter Model Block (Model 101)
            inverter_model = device.models.get(113)[0]
            if not inverter_model:
                print("SunSpec Inverter Block (Model 113) not found.")
                return
            if inverter_model.model.error_info:
                print(f"Error in model 113: {inverter_model.model.error_info}")
            
            print(inverter_model.model.get_dict())

            print("Raw Inverter Model Data:")
            for point_name, point in inverter_model.points.items():
                  print(f"{point_name}: {point.value} (type: {type(point.value)})")

            # Decode some example fields from the Inverter Model
            ac_power = inverter_model.points.get("W").value if "W" in inverter_model.points else None  # AC Power (W)
            dc_power = inverter_model.points.get("DCW").value if "DCW" in inverter_model.points else None  # DC Power (W)
            status = inverter_model.points.get("St").value if "St" in inverter_model.points else None  # Operating State

            print(f"AC Power: {ac_power} W")
            print(f"DC Power: {dc_power} W")
            print(f"Operating State: {status}")

            # If successful, break out of the retry loop
            break

        except ModbusClientTimeout:
            raise
        except Exception as e:
            if str(e).startswith("Connection error"):
                attempt += 1
                print(f"Attempt {attempt} failed: {e}")
                if attempt < retries:
                    print(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
                else:
                    print("All retry attempts failed. Exiting.")
        finally:
            # Ensure the connection is closed
            try:
                device.close()
            except:
                pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Read data from a SunSpec inverter.")
    parser.add_argument("ip", help="IP address of the inverter")
    parser.add_argument(
        "--port", type=int, default=502, help="Port number (default: 502)"
    )
    parser.add_argument(
        "--retries", type=int, default=3, help="Number of retry attempts (default: 3)"
    )
    parser.add_argument(
        "--delay", type=int, default=2, help="Delay between retries in seconds (default: 2)"
    )

    args = parser.parse_args()
    read_sunspec_inverter(args.ip, args.port, args.retries, args.delay)
