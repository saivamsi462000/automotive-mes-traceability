# Architecture: Automotive Assembly MES & Traceability

## ISA-95 landscape

```mermaid
flowchart TB
    subgraph L4["Level 4: ERP"]
        ERP[SAP / ERP<br/>orders · BOM · shipping]
    end
    subgraph L3["Level 3: MES"]
        FT[Rockwell FactoryTalk MES<br/>routing · sequencing · operator workflow]
        TRC[Traceability service<br/>serials · genealogy · NC/rework]
        SQL[(SQL Server<br/>traceability DB)]
        HIST[(FactoryTalk Historian / PI)]
    end
    subgraph L2["Level 2: SCADA / HMI"]
        IGN[Ignition Perspective / Vision<br/>station screens · andon · downtime]
    end
    subgraph L1["Level 1: Control"]
        PLC[Allen-Bradley ControlLogix / CompactLogix]
    end
    subgraph L0["Level 0: Devices"]
        LASER[DMC laser marker]
        SCAN[Barcode scanners]
        RFID[RFID read/write]
        NUT[DC nutrunners / torque controllers]
        PRESS[Servo press]
    end

    ERP --> FT
    FT <--> TRC
    TRC <--> SQL
    IGN <-->|OPC UA| PLC
    IGN <--> TRC
    PLC --> HIST
    PLC <--> LASER & SCAN & RFID & NUT & PRESS
```

## Station handshake (per operation)

```mermaid
sequenceDiagram
    participant PLC
    participant MES
    PLC->>MES: OPxx.Serial, ReqToMES = 1
    MES->>MES: Route interlock (unit known? previous ops OK? not on hold?)
    MES-->>PLC: MESRelease (1/0), MESReasonCode, MESAck = 1
    alt Released
        PLC->>PLC: Cycle (scan, press, torque, inspect)
        PLC->>MES: Results (torque/angle, force/depth, scans), ResultReady = 1
        MES->>MES: Validate vs window, write genealogy & results
        MES-->>PLC: ResultAck = 1 (and NC hold if NOK)
    else Blocked
        PLC->>PLC: Show reason on HMI, divert unit
    end
```

## Line layout: FSM-200 front suspension module

| Op | Station | Equipment | Data captured |
|---|---|---|---|
| OP10 | Knuckle load & serialize | Laser marker, DMC verifier | Serial, DMC grade |
| OP20 | Hub bearing press | Servo press, scanner | Bearing PN/lot/SN, force, depth |
| OP30 | Strut clamp bolt torque | 2-spindle nutrunner | Torque + angle per bolt, attempts |
| OP40 | Brake caliper install | Scanner, nutrunner | Caliper PN/lot/SN (variant check), torque + angle |
| OP50 | End-of-line inspection | Vision / manual checklist | Visual, orientation, DMC readability |
| OP60 | Pack & ship label | RFID writer, label printer | Rack ID, RFID EPC |
| RW01 | Rework bench | HMI | NC disposition, rework action, technician |

> This is a portfolio reconstruction with a fictitious product and data. It contains no Aztec Technologies or customer information.
