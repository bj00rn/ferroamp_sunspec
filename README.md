# Ferroamp ExtApi -> Sunspec ModbusTCP Server

This is currently a non functional experiment at the time of writing. Most (if not all) model points are not mapped correctly.

The general idea is to read data from Ferroamp local ExtApi and expose this data as a modbus server with a Sunspec compliant(ish) modbus model map data block to enable integration with devices that support Sunspec protocol.

An example is the newer Nibe model S heat pumps that can integrate Sunspec compliant inverters in MyUplink.


## Sunspec model map
* Three phase inverter model
* Three phase smart meter model
* TODO: Multiple MPPTT

## Data mapping from ExtApi

### Inverter Model (113)

| **Description** | **Label** | **Mandatory** | **Name** | **Size** | **Type**  | **Units** | **Symbols** | **ExtApi** | Comment |
|-----------------|-----------|---------------|----------|----------|-----------|-----------|-------------|------------|--|
| **Model identifier**                | Model ID                      | M             | ID         | 1        | uint16        |           |                                                                                                 | ?          |
| **Model length**                    | Model Length                  | M             | L          | 1        | uint16        |           |                                                                                                 | ?          |
| **AC Current**                      | Amps                          | M             | A          | 2        | float32       | A         |                                                                                                 | iextq?          | Sum of all phases
| **Phase A Current**                 | Amps PhaseA                   | M             | AphA       | 2        | float32       | A         |                                                                                                 | iextq?          | 
| **Phase B Current**                 | Amps PhaseB                   | M             | AphB       | 2        | float32       | A         |                                                                                                 | iextq?          |
| **Phase C Current**                 | Amps PhaseC                   | M             | AphC       | 2        | float32       | A         |                                                                                                 | iextq?          |
| Phase Voltage AB                    | Phase Voltage AB              |               | PPVphAB    | 2        | float32       | V         |                                                                                                 | ?          |
| Phase Voltage BC                    | Phase Voltage BC              |               | PPVphBC    | 2        | float32       | V         |                                                                                                 | ?          |
| Phase Voltage CA                    | Phase Voltage CA              |               | PPVphCA    | 2        | float32       | V         |                                                                                                 |           |
| **Phase Voltage AN**                | Phase Voltage AN              | M             | PhVphA     | 2        | float32       | V         |                                                                                                 | ul’?          |
| **Phase Voltage BN**                | Phase Voltage BN              | M             | PhVphB     | 2        | float32       | V         |                                                                                                 | ul’?          |
| **Phase Voltage CN**                | Phase Voltage CN              | M             | PhVphC     | 2        | float32       | V         |                                                                                                 | ?          |
| **AC Power**                        | Watts                         | M             | W          | 2        | float32       | W         |                                                                                                 | ?          |
| **Line Frequency**                  | Hz                            | M             | Hz         | 2        | float32       | Hz        |                                                                                                 | gridfreq?          |
| AC Apparent Power                   | VA                            |               | VA         | 2        | float32       | VA        |                                                                                                 | ?          |
| AC Reactive Power                   | VAr                           |               | VAr        | 2        | float32       | var       |                                                                                                 | ?          |
| AC Power Factor                     | PF                            |               | PF         | 2        | float32       | Pct       |                                                                                                 | ?          |
| **AC Energy**                       | WattHours                     | M             | WH         | 2        | float32       | Wh        |                                                                                                 | ?          | AC Lifetime
Energy
production
| DC Current                          | DC Amps                       |               | DCA        | 2        | float32       | A         |                                                                                                 | ?          |
| DC Voltage                          | DC Voltage                    |               | DCV        | 2        | float32       | V         |                                                                                                 | ?          |
| DC Power                            | DC Watts                      |               | DCW        | 2        | float32       | W         |                                                                                                 | ?          |
| **Cabinet Temperature**             | Cabinet Temperature           | M             | TmpCab     | 2        | float32       | C         |                                                                                                 | ?          |
| Heat Sink Temperature               | Heat Sink Temperature         |               | TmpSnk     | 2        | float32       | C         |                                                                                                 | ?          |
| Transformer Temperature             | Transformer Temperature       |               | TmpTrns    | 2        | float32       | C         |                                                                                                 | ?          |
| Other Temperature                   | Other Temperature             |               | TmpOt      | 2        | float32       | C         |                                                                                                 | ?          |
| **Operating state**                 | Operating State               | M             | St         | 1        | enum16        |           | OFF: 1, SLEEPING: 2, STARTING: 3, MPPT: 4, THROTTLED: 5, SHUTTING_DOWN: 6, FAULT: 7, STANDBY: 8 | ?          | Hardcode to "MPPT" for now
| Vendor specific operating state code| Vendor Operating State        |               | StVnd      | 1        | enum16        |           |                                                                                                 | ?          |
| **Event fields**                    | Event1                        | M             | Evt1       | 2        | bitfield32    |           | GROUND_FAULT: 0, DC_OVER_VOLT: 1, AC_DISCONNECT: 2, DC_DISCONNECT: 3, ...                      | ?          | Hardcode to nothing for now
| **Reserved for future use**         | Event Bitfield 2              | M             | Evt2       | 2        | bitfield32    |           |                                                                                                 | ?          | set to not implemented
| Vendor defined events               | Vendor Event Bitfield 1       |               | EvtVnd1    | 2        | bitfield32    |           |                                                                                                 | ?          |
| Vendor defined events               | Vendor Event Bitfield 2       |               | EvtVnd2    | 2        | bitfield32    |           |                                                                                                 | ?          |
| Vendor defined events               | Vendor Event Bitfield 3       |               | EvtVnd3    | 2        | bitfield32    |           |                                                                                                 | ?          |
| Vendor defined events               | Vendor Event Bitfield 4       |               | EvtVnd4    | 2        | bitfield32    |           |                                                                                                 | ?          |

## Smart Meter (Model 204)

| **Description**                     | **Label**                     | **Mandatory** | **Name**   | **Size** | **Type**      | **Units** | **Symbols**                                                                                     | **ExtApi** |
|-------------------------------------|-------------------------------|---------------|------------|----------|---------------|-----------|-------------------------------------------------------------------------------------------------|------------|
| **Model identifier**                | Model ID                      | M             | ID         | 1        | uint16        |           |                                                                                                 | ?          |
| **Model length**                    | Model Length                  | M             | L          | 1        | uint16        |           |                                                                                                 | ?          |
| **AC Current**                      | Amps                          | M             | A          | 2        | float32       | A         |                                                                                                 | ?          |
| **Phase A Current**                 | Amps PhaseA                   | M             | AphA       | 2        | float32       | A         |                                                                                                 | ?          |
| **Phase B Current**                 | Amps PhaseB                   | M             | AphB       | 2        | float32       | A         |                                                                                                 | ?          |
| **Phase C Current**                 | Amps PhaseC                   | M             | AphC       | 2        | float32       | A         |                                                                                                 | ?          |
| Phase Voltage AB                    | Phase Voltage AB              |               | PPVphAB    | 2        | float32       | V         |                                                                                                 | ?          |
| Phase Voltage BC                    | Phase Voltage BC              |               | PPVphBC    | 2        | float32       | V         |                                                                                                 | ?          |
| Phase Voltage CA                    | Phase Voltage CA              |               | PPVphCA    | 2        | float32       | V         |                                                                                                 | ?          |
| **Phase Voltage AN**                | Phase Voltage AN              | M             | PhVphA     | 2        | float32       | V         |                                                                                                 | ?          |
| **Phase Voltage BN**                | Phase Voltage BN              | M             | PhVphB     | 2        | float32       | V         |                                                                                                 | ?          |
| **Phase Voltage CN**                | Phase Voltage CN              | M             | PhVphC     | 2        | float32       | V         |                                                                                                 | ?          |
| **AC Power**                        | Watts                         | M             | W          | 2        | float32       | W         |                                                                                                 | ?          |
| **Line Frequency**                  | Hz                            | M             | Hz         | 2        | float32       | Hz        |                                                                                                 | ?          |
| AC Apparent Power                   | VA                            |               | VA         | 2        | float32       | VA        |                                                                                                 | ?          |
| AC Reactive Power                   | VAr                           |               | VAr        | 2        | float32       | var       |                                                                                                 | ?          |
| AC Power Factor                     | PF                            |               | PF         | 2        | float32       | Pct       |                                                                                                 | ?          |
| **AC Energy**                       | WattHours                     | M             | WH         | 2        | float32       | Wh        |                                                                                                 | ?          |
| DC Current                          | DC Amps                       |               | DCA        | 2        | float32       | A         |                                                                                                 | ?          |
| DC Voltage                          | DC Voltage                    |               | DCV        | 2        | float32       | V         |                                                                                                 | ?          |
| DC Power                            | DC Watts                      |               | DCW        | 2        | float32       | W         |                                                                                                 | ?          |
| **Cabinet Temperature**             | Cabinet Temperature           | M             | TmpCab     | 2        | float32       | C         |                                                                                                 | ?          |
| Heat Sink Temperature               | Heat Sink Temperature         |               | TmpSnk     | 2        | float32       | C         |                                                                                                 | ?          |
| Transformer Temperature             | Transformer Temperature       |               | TmpTrns    | 2        | float32       | C         |                                                                                                 | ?          |
| Other Temperature                   | Other Temperature             |               | TmpOt      | 2        | float32       | C         |                                                                                                 | ?          |
| **Operating state**                 | Operating State               | M             | St         | 1        | enum16        |           | OFF: 1, SLEEPING: 2, STARTING: 3, MPPT: 4, THROTTLED: 5, SHUTTING_DOWN: 6, FAULT: 7, STANDBY: 8 | ?          |
| Vendor specific operating state code| Vendor Operating State        |               | StVnd      | 1        | enum16        |           |                                                                                                 | ?          |
| **Event fields**                    | Event1                        | M             | Evt1       | 2        | bitfield32    |           | GROUND_FAULT: 0, DC_OVER_VOLT: 1, AC_DISCONNECT: 2, DC_DISCONNECT: 3, ...                      | ?          |
| **Reserved for future use**         | Event Bitfield 2              | M             | Evt2       | 2        | bitfield32    |           |                                                                                                 | ?          |
| Vendor defined events               | Vendor Event Bitfield 1       |               | EvtVnd1    | 2        | bitfield32    |           |                                                                                                 | ?          |
| Vendor defined events               | Vendor Event Bitfield 2       |               | EvtVnd2    | 2        | bitfield32    |           |                                                                                                 | ?          |
| Vendor defined events               | Vendor Event Bitfield 3       |               | EvtVnd3    | 2        | bitfield32    |           |                                                                                                 | ?          |
| Vendor defined events               | Vendor Event Bitfield 4       |               | EvtVnd4    | 2        | bitfield32    |           |                                                                                                 | ?          |
