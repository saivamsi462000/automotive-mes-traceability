# Ignition Perspective / Vision HMI Screen Specification

## 1. Line overview (Perspective, wall-mounted 55")

| Area | Content | Binding |
|---|---|---|
| Header | Line state (Running / Faulted / Starved / Blocked) colour-coded | `[Line1]Line.State` |
| Station tiles OP10–OP60 | Current serial, last result (OK/NOK), cycle time, MES release status | `OPxx.Serial`, `OPxx.MESRelease`, SQL last result |
| KPI strip | Units this shift, FPY per station, RTY, open NCs | Named queries `first_pass_yield_by_station`, `open_nonconformances` |
| Andon bar | Active andon by type (quality / material / maintenance) with timer | `[Line1]Line.Andon`, `andon_event` |

## 2. Station screen (Vision client at each station)

- Large **OK / NOK / BLOCKED** indicator, with the reason text mapped from `MESReasonCode`
- Work instruction image for the current variant
- Torque stations: live torque/angle per bolt against the window, attempt counter
- Scan stations: expected part number vs scanned part number
- Andon buttons: Quality / Material / Maintenance

## 3. Rework bench (RW01)

- Scan the serial to see the open NC (op, description, timestamp)
- Birth history table (named query `unit_birth_history`)
- Disposition selector: REWORK / SCRAP, with an action text and technician badge scan
- Submit, which closes the NC and releases the unit back to the failed operation

## 4. Traceability search (Perspective)

- Search by serial → birth history
- Search by lot → containment list (named query `containment_by_lot`) with rack and RFID, exportable to CSV
- Search by date range / op → torque results export for SPC

## 5. Downtime & alarms

- Alarm journal for station faults
- Downtime reason entry when the line state ≠ Running for more than 60 s
