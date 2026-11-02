# Project Guidelines

## Architecture

- Keep the SunSpec core independent of MQTT: `device.py` owns library-backed
  models and atomic register snapshots; `server.py` supplies Modbus transport;
  `telemetry.py` maps Ferroamp payloads; `mqtt.py` handles async delivery;
  `ferroamp_sunspec.py` wires the components together.
- Reuse pysunspec2 definitions, offsets, encoding, and unavailable sentinels.
  Do not introduce handwritten model layouts or vendor emulation to accommodate
  a client without verified requirements.
- Publish changes through `update_points()`. Direct model mutation does not
  publish a register snapshot. Preserve atomic validation and partial-update
  behavior: omitted points retain values; `None` marks them unavailable.

## Telemetry invariants

- The default chain is Common model 1, inverter 113, and wye grid meter 213.
  Keep inverter, grid, and household-load measurements distinct.
- Inverter active power is `-sum(pinv)` (positive generation); grid active power
  preserves `pext` signs (positive import, negative export), both total and per
  phase. These directions are supported by installation observations, not an
  explicit revision E sign definition. Do not reverse reactive power by analogy.
- Float-model power is in watts without a scale factor. Parse uint64 energy
  counters as integers before summing and divide mJ by 3,600,000 for Wh.
- Use `sext` for total grid apparent power; do not estimate phase apparent
  power. External voltage and grid frequency populate the grid meter only.
- Leave undocumented state, PF, and unsupported measurements unavailable,
  rather than fabricating zeros or guessing conventions.
- Do not substitute `ppv` or SSO `upv * ipv` for inverter `DCW`: Ferroamp's
  shared DC link can include battery flows and converter losses. Those values
  describe PV production, not necessarily inverter DC input.
- See [README.md](README.md) for the mapping table, specification reference,
  ambiguities, and unavailable-point rationale.

## Integration and diagnostics

- On the tested NIBE S1256, production and consumption displays worked after
  selecting **4.2.2 > Energy meter > Smart meter**. Check configuration before
  changing standard point meanings; surplus-based control is not yet verified.
- `--trace-modbus` logs requests and snapshot-derived response values. Accepted
  reads prove neither client interpretation nor control behavior. Trace output
  may contain identity fields; review it before sharing.
- Use a distinct application logger such as `ferroamp.mqtt`: aiomqtt sets the
  logger named `mqtt` to WARNING, suppressing application INFO messages there.

## Validation

- Install dependencies with `pip install -r requirements.txt` in a virtual
  environment. Respect dependency API bounds; upgrades require adapting and
  testing the transport, not merely removing upper bounds.
- Run `python -m pytest -q`; target related test files for focused changes.
  Tests use loopback TCP and do not require Ferroamp hardware or an MQTT broker.
- Mapping changes should cover units, import/export directions, unavailable
  points, and real pysunspec2 TCP readback. Update the related README notes.
- Documentation-only edits do not require Python tests; check formatting with
  `git diff --check`.
