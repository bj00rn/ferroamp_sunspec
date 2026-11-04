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

The default chain contains Common model **1**, three-phase inverter model
**113**, wye-connected AC meter model **213**, and the end marker. The inverter
and grid meter remain separate so their readings are not conflated. Model
lengths, field order, types, and scale factors come from pysunspec2's bundled
definitions.

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

## Docker

Build and run the Alpine-based MQTT bridge:

```sh
docker build -t ferroamp-sunspec .
docker run --rm -e MQTT_HOST=192.0.2.10 -p 1502:502 ferroamp-sunspec
```

Configure the bridge using the environment variables described below, or append
CLI options, for example `ferroamp-sunspec --log-level DEBUG`. The default
container Modbus port is 502; if changing `MODBUS_PORT`, adjust the container
side of the port mapping too.

## Standalone server (no MQTT)

```sh
python server.py --host 127.0.0.1 --port 1502 --trace-modbus
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
        213: {"W": -400.0, "TotWhImp": 12000.0},
    })
    await SunspecServer(device, host="127.0.0.1", port=1502).run_forever()


asyncio.run(main())
```

Other sources can call `update_points()` without knowing anything about MQTT.
Values use the units and representations of the pysunspec2 model points.
`SunspecDevice` accepts an ordered `model_ids` sequence for other fixed model
chains, with Common model 1 first. Updates address top-level points by model ID
and name.

The `models` lookup exposes native pysunspec2 models (for example
`device.models[113][0]`), but direct point mutation does **not** publish a
register snapshot; use `update_points()`.

## MQTT bridge

```sh
python ferroamp_sunspec.py \
  --mqtt-host 192.0.2.10 \
  --mqtt-port 1883 \
  --mqtt-topic extapi/data/ehub \
  --modbus-port 1502 \
  --trace-modbus
```

Both entry points accept `--base-addr` (default **40000**) and `--unit-id`
(default **1**, range 1..247). The bridge accepts `--modbus-host`; the standalone
server accepts `--host`. The default bind address is `0.0.0.0`, and the default
TCP port is 502, which may require elevated privileges.
Modbus TCP client connections and disconnections are logged at INFO with the
remote IP address and port, independently of request tracing. Modbus TCP does
not provide a separate client ID; the request unit ID identifies the addressed
device, not the client.
The optional `--trace-modbus` flag logs each request's unit ID, function code,
register address, count, and whether the request is accepted. Response logs
include returned register words and decoded values for fully contained SunSpec
points, taken from the same register snapshot. This includes identity fields
when requested, so review traces before sharing them. Use tracing to observe
SunSpec discovery and verify the measurements served to a client; tracing is
off by default.

The bridge, standalone server, and MQTT listener accept `--log-level` with
`DEBUG`, `INFO` (default), `WARNING`, `ERROR`, or `CRITICAL` (case-insensitive).
For example, add `--log-level DEBUG` to see reads of unsupported points.
DEBUG logging can include telemetry payloads and protocol details; review logs
before sharing them. INFO request/response traces require `--trace-modbus`
and a log level of INFO or DEBUG.

### Environment configuration

All three entry points also read arguments from environment variables.
Precedence is **command line > environment > built-in
defaults**. Variable names are the uppercase argument names with hyphens
replaced by underscores, for example `MQTT_HOST`, `MODBUS_PORT`,
`STALE_TIMEOUT`, `BASE_ADDR`, `UNIT_ID`, `LOG_LEVEL`, and `TRACE_MODBUS`.
The standalone server uses `HOST` and `PORT`; the MQTT listener uses `BROKER`,
`PORT`, `CLIENT_ID`, and `TOPIC`, matching their respective CLI arguments.

Example:

```sh
export MQTT_HOST=192.0.2.10
export MODBUS_PORT=1502
export STALE_TIMEOUT=5
export LOG_LEVEL=INFO
export TRACE_MODBUS=false
python ferroamp_sunspec.py
```

Run `python ferroamp_sunspec.py` to use these settings, or override individual
values, for example `python ferroamp_sunspec.py --log-level DEBUG`.
Boolean variables accept `true/false`, `yes/no`, `on/off`, or `1/0`,
case-insensitively. Invalid numeric, boolean, or log-level configuration is
reported as an argument error. Dotenv files are not loaded automatically.

The bridge consumes MQTT messages directly on the asyncio event loop, with no
application-managed MQTT worker thread or Paho callbacks. The Modbus server
starts without waiting for MQTT, exposing device identity and unavailable
measurements until valid telemetry arrives. It remains available during MQTT
outages, with stale points expiring as described below. Connection and
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

## ExtApi mappings

Mappings follow the [Ferroamp External API specification, revision E,
section 4.1.2, pages 5-8](https://ferroamp.com/wp-content/uploads/2023/04/Ferroamp-External-API-specification-E-1.pdf).
The bridge consumes **EnergyHub** (`extapi/data/ehub`) messages and publishes
separate inverter and external/grid measurements as models **113** and **213**.
The inverter model uses inverter-side measurements; the meter model uses
external/grid-side measurements.

| ExtApi input | SunSpec 113 inverter | SunSpec 213 grid meter | Conversion |
|---|---|---|---|
| `gridfreq.val` | - | `Hz` | Estimated grid frequency, Hz |
| `ul.L1/L2/L3` | - | `PhVphA/B/C`, `PhV` | External/grid voltage, V; meter `PhV` is the phase average |
| `il.L1/L2/L3` | `AphA/B/C`, `A` | - | Inverter RMS A; sum for total |
| `iext.L1/L2/L3` | - | `AphA/B/C`, `A` | Grid RMS A; sum for total |
| `pinv.L1/L2/L3` | `W` | - | Negated sum of active W; positive for generation |
| `pinvreactive.L1/L2/L3` | `VAr` | - | Sum of reactive power |
| `pext.L1/L2/L3` | - | `WphA/B/C`, `W` | Grid active W, signs preserved; sum for total |
| `pextreactive.L1/L2/L3` | - | `VARphA/B/C`, `VAR` | Grid reactive power; sum for total |
| `sext.val` | - | `VA` | Grid apparent VA |
| `winvprodq.L1/L2/L3` | `WH` | - | Sum inverter production, mJ / 3,600,000 -> Wh |
| `wextprodq.L1/L2/L3` | - | `TotWhExpPhA/B/C`, `TotWhExp` | Grid production/export, mJ / 3,600,000 -> Wh |
| `wextconsq.L1/L2/L3` | - | `TotWhImpPhA/B/C`, `TotWhImp` | Grid consumption/import, mJ / 3,600,000 -> Wh |
| `udc.pos`, `udc.neg` | `DCV` | - | DC-link voltage span: pos - neg, V |

The required `sext.val` maps directly to model 213 `VA`. The API does not
provide phase-specific apparent power, so model 213 `VAphA/B/C` remain
unavailable; they are not estimated from `ul × iext`. The revision E example's
`ul × iext` phase products sum to 2442.46 VA, while `sext` is 2435.31 VA.
The API defines `ul` as external voltage and `gridfreq` as estimated grid
frequency, so neither is mapped to inverter model 113. No inverter-side voltage
is provided to derive inverter apparent power.

**Inverter active power polarity is reversed**: model 113 `W` is
`-sum(pinv.L1/L2/L3)`, making generation positive for the observed installation.
A live sample reported `pinv` totaling -594.257 W alongside solar production;
the mapper now exposes +594.257 W. Positive `pinv` becomes negative SunSpec
power, not an absolute value. This is an installation-derived assumption, not
a polarity convention explicitly established by revision E; confirm it on
other installations and verify NIBE's displayed production after restarting.
**Grid active power polarity is preserved**: model 213 `WphA/B/C` receive
`pext` phases, and `W` their sum. For the observed installation, import is
positive and export negative, matching the Fronius grid-location convention.
The experimental grid-sign reversal did not correct NIBE's consumption
display and has been removed. Positive inverter generation in model 113 and
negative grid export in model 213 describe different measurement locations.
All reactive power retains its input signs; energy counters are unchanged.
Revision E describes `pinvreactive` as active power and lists W for
`pextreactive`, despite naming both fields as reactive power. The mapper treats
both as reactive power according to their names and example, and maps them to
SunSpec reactive-power points.
Validate power direction against the installation before using these values
for control. Inverter production energy maps from `winvprodq`; inverter
consumption is not mapped because model 113 has no separate consumption
counter. Grid export/import energy maps from `wextprodq`/`wextconsq`,
independently of instantaneous power polarity.

The uint64 energy counters are parsed and summed as integers before converting
units. Models 113/213 represent energy as float32, so large lifetime totals
lose precision when encoded in the SunSpec register map.

### SunSpec definition references and conformance limitations

The official legacy definitions for
[inverter model 113](https://github.com/sunspec/models/blob/master/smdx/smdx_00113.xml)
and [meter model 213](https://github.com/sunspec/models/blob/master/smdx/smdx_00213.xml)
define the point names, layouts, types, and units used here. Both expose
float32 power in watts and energy in Wh without scale factors. Model 113
describes total current as the sum of active phases; model 213 describes
`PhV` as the average phase-to-neutral voltage of active phases.

Some points marked mandatory in those definitions cannot be populated from
the documented EnergyHub telemetry:

| Model | Mandatory points left unavailable | Reason |
|---|---|---|
| 113 | `PhVphA/B/C`, `Hz` | No separately identified inverter-side voltage or frequency |
| 113 | `TmpCab` | No EnergyHub cabinet temperature |
| 113 | `St`, `Evt1`, `Evt2` | No documented EnergyHub state/event translation |
| 213 | `PPV`, `PPVphAB/BC/CA` | No line-to-line voltage measurements |
| 213 | `Evt` | No documented EnergyHub event translation |

These are intentional data-availability limitations, not optional-point
omissions. The bridge does not fabricate readings or healthy states to fill
mandatory points. Library-defined encoding and successful NIBE interoperability
do not establish full SunSpec conformance; this project makes no conformance
or certification claim.

The 2021 SunSpec DER Information Model Specification describes models
701-713, not these legacy models. Its scaled-integer layouts must not be
applied to 113/213. The legacy XML definitions alone do not establish the
Ferroamp-to-SunSpec power polarity or prescribe stale-data timeouts; the
mapping assumptions and bridge expiration policy are documented separately
below.

### Deliberately unavailable points

Unavailable means the SunSpec **not-implemented sentinel**, not a measured zero
or an indication that the device is healthy, off, or disconnected. pysunspec2
clients decode these values as `None`; float32 points use NaN on the wire and
enum/bitfield points use their type-specific sentinel. Consumers must handle
these points as unknown rather than substituting zero.

#### Ambiguous operating state and events

Revision E describes EnergyHub `state` only as a uint32 bitmask; it does not
define the meaning of its bits. SunSpec model 113 `St` is an enum, so copying
the mask into it would invent an operating state. The specification also
supplies no EnergyHub event/alarm mapping. Consequently, model 113 `St`,
`StVnd`, and `Evt1`, `Evt2`, `EvtVnd1..4`, and model 213 `Evt` remain
unavailable. A missing event value does **not** mean "no faults." The ESO/SSO
fault definitions elsewhere in the specification describe different devices
and are not applied to EnergyHub state. Mapping these points requires
documented EnergyHub bit definitions and an explicit translation to SunSpec
states/events.

#### Power factor

Inverter model 113 `PF` and meter model 213 `PF`, `PFphA/B/C` remain
unavailable. Although active and apparent power can provide a ratio, revision
E does not establish how power direction and leading/lagging reactive power
correspond to the required SunSpec power-factor sign convention. A naive ratio
could therefore report a misleading sign.

Implementing these points requires confirmed sign/representation conventions,
matching measurements from the same message, and defined handling of zero
apparent power. Unknown or undefined PF must not be reported as zero or unity.

#### Unsupported measurements and fields

- `iext` is grid-side RMS current, not inverter current; it populates model 213
  only. `iextq`/`ilq` and `iextd`/`ild` are active/reactive current components,
  not RMS current, so they do not populate either model's `A`. Load power
  (`pload`) is not assigned to inverter or meter power.
- The API provides external voltage (`ul`) and estimated grid frequency
  (`gridfreq`), but no inverter-side voltage or frequency. Consequently, model
  113 `PhVphA/B/C`, `Hz`, and `VA` remain unavailable; `ul` and `gridfreq`
  populate model 213 only.
- The API provides only total grid apparent power (`sext`), so model 213
  `VAphA/B/C` remain unavailable rather than being estimated from voltage and
  current whose products do not match `sext` in the revision E example.
- Line-to-line voltages cannot be measured from RMS phase voltages alone
  without assuming phase angles. `PPVphAB/BC/CA` remain unavailable.
- `sext` is external/grid apparent power; it populates model 213 `VA`, not
  inverter model 113 `VA`.
- `ppv` and `pbat` are not measurements of the inverter's total DC input power.
  Model 113 `DCW` and `DCA` remain unavailable. `udc.pos - udc.neg` maps to
  inverter `DCV`; it has no equivalent point in model 213.
- No EnergyHub temperature measurements are specified, so model 113
  `TmpCab`, `TmpSnk`, `TmpTrns`, and `TmpOt` remain unavailable.
- Available inverter production energy maps to model 113 `WH`; inverter
  consumption has no corresponding point/counter in model 113. Grid production
  and consumption map to model 213 `TotWhExp` and `TotWhImp`. No reactive or
  apparent-energy counters are provided, so model 213 `TotVAh*` and
  `TotVArh*` remain unavailable.
- Load/PV/battery totals, SoC/SoH, timestamps, throttling details, and other
  system status are not represented in these AC models.
- ESO/SSO/ESM topics, MPPT/battery models, and inverter controls are not
  implemented.

Unsupported payload fields are ignored rather than stored in unrelated SunSpec
points. These unavailable-point notes describe the MQTT mapping: callers of
`update_points()` may explicitly supply supported SunSpec points when they have
an authoritative source for their values.

The MQTT bridge expires each mapped point independently after five
seconds without a valid update by default. Expiration writes the SunSpec
not-implemented value and logs a warning; the next valid update restores the
point and logs recovery.
Each Modbus read overlapping an expired point also logs a warning with the
unit ID, function, address, register count, and stale point names, even without
`--trace-modbus`. Never-populated unsupported points do not trigger this warning.
Reads overlapping unavailable non-stale points are logged at DEBUG instead;
this includes unsupported or never-populated measurements. Enable DEBUG for
the server logger to see them.
Override the interval with `--stale-timeout SECONDS`
on `ferroamp_sunspec.py`. A partial message refreshes only the points it
contains; omitted fields keep their current value until they expire. Standalone
users of `SunspecDevice` do not get automatic expiration.

Partial messages are supported. Recognized fields must contain valid finite
numbers and complete phase triples. RMS voltages/currents and apparent power
must be nonnegative; energy counters must be uint64 integers. Invalid messages
are logged and rejected without changing any points. Unrecognized fields are
ignored.

## Observed NIBE SunSpec reads

A NIBE heat-pump trace captured on 2026-11-02 shows reads of the following
points. This is observed client behavior, not a documented requirement for
every NIBE model or firmware version. Addresses below are zero-based Modbus
wire addresses for this server's default model chain and base address 40000.

| Model | Points read | Start address | Register count | MQTT mapping |
|---|---|---|---|---|
| 1 Common | `Mn` | 40004 | 16 | Ferroamp manufacturer identity |
| 1 Common | `SN` | 40052 | 16 | Profile serial number |
| 113 inverter | `W` | 40092 | 2 | Negated sum of `pinv` phases; positive for generation |
| 113 inverter | `WH` | 40102 | 2 | Sum of `winvprodq` phases, converted to Wh |
| 113 inverter | `DCV` | 40106 | 2 | `udc.pos - udc.neg` |
| 113 inverter | `DCW` | 40108 | 2 | Unavailable (float32 NaN) |
| 213 grid meter | `AphA/B/C` | 40136 | 6 | `iext.L1/L2/L3` |
| 213 grid meter | `PhVphA/B/C` | 40144 | 6 | `ul.L1/L2/L3` |
| 213 grid meter | `Hz` | 40158 | 2 | `gridfreq.val` |
| 213 grid meter | `W` | 40160 | 2 | Sum of `pext` phases |
| 213 grid meter | `WphA/B/C` | 40162 | 6 | `pext.L1/L2/L3` |

The trace also includes reads of the `SunS` signature, model IDs/lengths for
models 1, 113, and 213, and the end marker. All observed request ranges were
accepted. The requested meter phase powers represent net grid import/export,
not household phase loads (`pload`). Inverter power can include battery
contribution and is not necessarily solar-only production.

Repeated polling supports protocol interoperability, but does not prove that
NIBE accepts the unavailable `DCW`, displays the values correctly, or uses them
correctly for PV control. Confirm power polarity and actual heat-pump behavior
on the installation. Points not read in this capture should not be assumed
unnecessary in other configurations.

### NIBE energy-meter configuration and display observations

On the tested NIBE S1256 with firmware 4.14.6, set **menu 4.2.2 > Energy
meter > Smart meter** to select the external smart meter as the energy-meter
source. After selecting this option, the user confirmed that "total measured
consumption" displays correctly. The installation was initially missing this
configuration. SunSpec
meter polling alone does not establish that the smart meter is selected for
the energy dashboard.

Testing with a NIBE S1256 running firmware 4.14.6 confirmed that reversing
`pinv` polarity made the displayed produced power agree with inverter AC
generation. The Solar PV page's "total measured consumption" remained around
0.5-0.8 kW while household consumption was around 11 kW. Reversing grid-meter
power did not resolve this, so that experiment was reverted; grid import
remains positive and export negative.

Response tracing confirmed that model 213 returned approximately 10.5 kW of
grid power in watts, with correctly encoded float32 phase values. This rules
out a W/kW encoding error for the captured responses, but does not establish
how NIBE uses those values.

The missing **Energy meter > Smart meter** selection was subsequently
identified by the user. Check this setting before investigating scaling or
changing grid-meter mappings. The earlier hypothesis that the display falls
back to the heat pump's own consumption was not verified. Production and total
measured consumption displays are now confirmed working on this installation;
surplus-based control requires separate installation verification.

The [official NIBE S-series firmware changelog](https://www.nibe.eu/webdav/files/myuplink_changelog/nibe-n.pdf)
documents Fronius and SolarEdge SunSpec Smart Meter support in 3.5.5 (page 21),
SunSpec 700-series PV inverter support in 4.11.5 (page 6), and a fix for reading
SunSpec floating-point registers in 4.14.6 (page 2). The menu configuration
above was reported from the tested installation, not established by these
release notes.

Use `--trace-modbus` to inspect another installation. The current datastore
can log a request twice because validation also occurs during register access;
duplicate trace lines do not necessarily mean duplicate network requests.

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
