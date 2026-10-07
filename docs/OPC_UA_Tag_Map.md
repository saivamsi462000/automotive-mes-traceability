# OPC UA Tag Map

Namespace: `ns=2;s=[Line1]<Op>.<Tag>` (Ignition OPC UA server → Allen-Bradley Logix driver).
A live snapshot from the simulation is in `output/opcua_tag_snapshot.json`.

## Handshake tags (every station)

| Tag | Type | Writer | Description |
|---|---|---|---|
| `OPxx.Serial` | String | PLC | Serial read from the DMC at station entry |
| `OPxx.ReqToMES` | Bool | PLC | Request a route check / release |
| `OPxx.MESRelease` | Bool | MES | 1 = process allowed, 0 = blocked |
| `OPxx.MESReasonCode` | Int | MES | See reason codes below |
| `OPxx.MESAck` | Bool | MES | Request handled |
| `OPxx.ResultReady` | Bool | PLC | Cycle results available |
| `OPxx.ResultAck` | Bool | MES | Results stored |

## Process tags

| Tag | Type | Unit | Station |
|---|---|---|---|
| `OP20.Press.Force` | Real | kN | OP20 |
| `OP20.Press.Depth` | Real | mm | OP20 |
| `OP20.Scan.Barcode` | String | — | OP20 |
| `OP30.Bolt1.Torque` / `OP30.Bolt2.Torque` | Real | Nm | OP30 |
| `OP30.Bolt1.Angle` / `OP30.Bolt2.Angle` | Real | deg | OP30 |
| `OP40.Scan.Barcode` | String | — | OP40 |
| `OP40.Bolt1.Torque` / `OP40.Bolt2.Torque` | Real | Nm | OP40 |
| `OP40.Bolt1.Angle` / `OP40.Bolt2.Angle` | Real | deg | OP40 |
| `OP50.Inspect.Visual` | Bool | — | OP50 |
| `OP60.RFID.EPC` | String | — | OP60 |
| `Line.State` | Int | — | 0 Stopped, 1 Running, 2 Faulted, 3 Starved, 4 Blocked |
| `Line.Andon` | Int | — | 0 none, 1 quality, 2 material, 3 maintenance |

## Reason codes (`MESReasonCode`)

| Code | Meaning | HMI action |
|---|---|---|
| 0 | OK | Cycle |
| 1 | Unknown serial | Send to OP10 / re-mark |
| 2 | Previous operation not complete | Return unit to the missing operation |
| 3 | Operation already complete | Pass through |
| 4 | Unit on non-conformance hold | Divert to RW01 |
| 5 | Wrong part for variant | Present the correct part, rescan |
| 6 | Component lot on containment hold | Quarantine the part, call quality |
| 7 | Component serial already used | Quarantine the part (duplicate label) |
| 8 | Unit scrapped | Divert to scrap |
