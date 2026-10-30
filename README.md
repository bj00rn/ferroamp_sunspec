# Ferroamp ExtApi -> SunSpec Modbus TCP

Expose Ferroamp telemetry as a SunSpec Modbus TCP device. The SunSpec core can
also run independently, without MQTT or Ferroamp hardware.

## Architecture

- [device.py](device.py): transport-independent SunSpec device and Ferroamp
  profile. Uses **pysunspec2** model definitions, model/point objects, register
  offsets, type encoding, and not-implemented values. There are no handwritten
  model layouts or payload builders.
- [server.py](server.py): read-only Modbus TCP transport using **pymodbus**.
  pysunspec2 provides the SunSpec data model and client, but not a TCP server.
- [telemetry.py](telemetry.py): Ferroamp ExtApi payload-to-point mapping.
- [mqtt.py](mqtt.py): asyncio-native MQTT connection, subscription, and raw
  message delivery using **aiomqtt**.
- [ferroamp_sunspec.py](ferroamp_sunspec.py): application wiring and lifecycle.

The default chain contains Common model **1**, three-phase float inverter
**113**, delta-connected float meter **214**, and the end marker. Model lengths
and field order come from pysunspec2's bundled definitions.

Unpopulated measurements, operating states, and event flags are exposed as
SunSpec **not implemented**, not fabricated zero readings. Updates are validated
and encoded before a complete register snapshot is published. Omitted points
retain their last value; explicitly assigning `None` marks a point unavailable.
Each register read sees one complete snapshot; separate Modbus requests may
observe different updates.

## Installation

Requires Python 3.11 or newer.

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

The pysunspec2 version is pinned because its unavailable float encoding is
important for interoperability. pymodbus is constrained to its supported 3.8 API.

## Standalone server (no MQTT)

```sh
python server.py --host 127.0.0.1 --port 1502
```

This serves device identity and unavailable telemetry until values are provided
programmatically:

```python
import asyncio

from device import FerroampDevice
from server import SunspecServer


async def main():
    device = FerroampDevice()
    device.update_points({
        113: {"W": 3200.0, "Hz": 50.0, "PhVphA": 230.0},
        214: {"W": -400.0, "TotWhImp": 12000.0},
    })
    await SunspecServer(device, host="127.0.0.1", port=1502).run_forever()


asyncio.run(main())
```

Other sources can call `update_points()` without knowing anything about MQTT.
Values use the raw units in the SunSpec definition; for scaled integer models,
provide raw integer values and their scale-factor points. `SunspecDevice` accepts
an ordered `model_ids` sequence for other fixed model chains, with Common model
1 first. Updates address top-level points by model ID and name.

The `models` lookup exposes native pysunspec2 models (for example
`device.models[113][0]`), but direct point mutation does **not** publish a register
snapshot; use `update_points()`.

## MQTT bridge

```sh
python ferroamp_sunspec.py \
  --mqtt-host 192.0.2.10 \
  --mqtt-port 1883 \
  --mqtt-topic extapi/data/ehub \
  --modbus-port 1502
```

Both entry points accept `--base-addr` (default **40000**) and `--unit-id`
(default **1**, range 1..247). The bridge accepts `--modbus-host`; the standalone
server accepts `--host`. The default bind address is `0.0.0.0`, and the default
TCP port is 502, which may require elevated privileges.

The bridge consumes MQTT messages directly on the asyncio event loop, with no
application-managed MQTT worker thread or Paho callbacks. Connection and
subscription failures are logged and retried every five seconds; each
reconnection subscribes again. Shutdown cancels message consumption (including
connection attempts or retry waits) and closes the MQTT client context before
stopping the Modbus server. aiomqtt itself uses Paho internally.

The base address is the actual **zero-based Modbus wire address**, not a
one-based holding-register reference. The `SunS` signature starts at 40000;
Common model 1 starts at 40002. Only the configured unit ID is served. Holding
register reads (function 3) are supported; writes and other data tables are
rejected. No authentication is provided by this Modbus TCP endpoint; bind it
only to a trusted network.

## Existing ExtApi mappings and limitations

The bridge deliberately preserves the experiment's existing mappings while
moving them outside the SunSpec models:

| ExtApi input | Model 113 points |
|---|---|
| `gridfreq.val` | `Hz` |
| `iextq.L1/L2/L3` | `AphA/B/C`, sum to `A` |
| `ul.L1/L2/L3` | `PhVphA/B/C` |
| `pload.L1/L2/L3` | sum to `W` |
| `sext.val` | `VA` |
| `winvprodq.L1/L2/L3` | sum to `WH` |

**These are not verified physical mappings.** In particular, reactive grid
current and load power may not describe inverter current and production.
Energy units and sign conventions need confirmation against the Ferroamp API.
Do not use the bridge's telemetry for control decisions until verified.

Model 214 is correctly encoded and can be populated through `update_points()`,
but has no automatic ExtApi mapping yet. Whether model 213 (wye) is more
appropriate depends on the installation. MPPT/battery models and inverter
controls are not implemented. Missing telemetry is retained indefinitely;
there is currently no stale-data timeout.

Partial messages are supported. Recognized fields must contain valid finite
numbers and complete phase triples; invalid messages are logged and rejected
without changing any points. Unrecognized fields are ignored.

## Verification

```sh
python -m pytest -q
python client.py 127.0.0.1 --port 1502
```

Tests cover library-defined layouts and unavailable values, atomic updates,
telemetry validation, read-only register access, wire addressing, startup and
shutdown, and real pysunspec2 client discovery/readback over loopback TCP at
base addresses 0, 40000, and 50000. No MQTT broker or Ferroamp hardware is
required for the tests.
