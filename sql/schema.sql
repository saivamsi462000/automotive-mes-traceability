-- Automotive MES traceability data model (ANSI SQL; SQLite for the demo, SQL Server in production)

CREATE TABLE unit (
    serial        VARCHAR(20) PRIMARY KEY,
    variant       VARCHAR(20) NOT NULL,
    dmc           VARCHAR(60) NOT NULL UNIQUE,
    status        VARCHAR(10) NOT NULL CHECK (status IN ('WIP', 'NC_HOLD', 'PACKED', 'SCRAP')),
    rack          VARCHAR(12),
    rfid_epc      VARCHAR(24),
    created_at    VARCHAR(20) NOT NULL
);

CREATE TABLE station_result (
    id            INTEGER PRIMARY KEY,
    serial        VARCHAR(20) NOT NULL REFERENCES unit(serial),
    op            VARCHAR(6)  NOT NULL,
    result        VARCHAR(12) NOT NULL,     -- OK / NOK / SCAN_REJECT / REWORK / SCRAP
    detail        VARCHAR(200),
    ts            VARCHAR(20) NOT NULL
);

CREATE TABLE genealogy (
    serial            VARCHAR(20) NOT NULL REFERENCES unit(serial),
    op                VARCHAR(6)  NOT NULL,
    component_type    VARCHAR(20) NOT NULL,
    part_number       VARCHAR(20) NOT NULL,
    lot               VARCHAR(20) NOT NULL,
    component_serial  VARCHAR(30) NOT NULL UNIQUE,   -- a component can only be used once
    ts                VARCHAR(20) NOT NULL
);

CREATE TABLE torque_result (
    serial      VARCHAR(20) NOT NULL REFERENCES unit(serial),
    op          VARCHAR(6)  NOT NULL,
    bolt        INT NOT NULL,
    attempt     INT NOT NULL,
    torque_nm   DECIMAL(6,2) NOT NULL,
    angle_deg   DECIMAL(6,2) NOT NULL,
    result      VARCHAR(3) NOT NULL CHECK (result IN ('OK', 'NOK')),
    ts          VARCHAR(20) NOT NULL
);

CREATE TABLE press_result (
    serial      VARCHAR(20) NOT NULL REFERENCES unit(serial),
    force_kn    DECIMAL(6,2) NOT NULL,
    depth_mm    DECIMAL(6,3) NOT NULL,
    result      VARCHAR(3) NOT NULL,
    ts          VARCHAR(20) NOT NULL
);

CREATE TABLE nonconformance (
    nc_id        INTEGER PRIMARY KEY,
    serial       VARCHAR(20) NOT NULL REFERENCES unit(serial),
    op           VARCHAR(6)  NOT NULL,
    description  VARCHAR(200) NOT NULL,
    status       VARCHAR(6)  NOT NULL CHECK (status IN ('OPEN', 'CLOSED')),
    disposition  VARCHAR(10),
    action       VARCHAR(200),
    closed_by    VARCHAR(30),
    opened_at    VARCHAR(20) NOT NULL,
    closed_at    VARCHAR(20)
);

CREATE TABLE lot_hold (
    lot          VARCHAR(20) NOT NULL,
    reason       VARCHAR(200) NOT NULL,
    held_at      VARCHAR(20) NOT NULL,
    released_at  VARCHAR(20)
);

CREATE TABLE andon_event (
    id       INTEGER PRIMARY KEY,
    op       VARCHAR(6)  NOT NULL,
    kind     VARCHAR(12) NOT NULL,     -- QUALITY / MATERIAL / MAINTENANCE
    message  VARCHAR(200),
    ts       VARCHAR(20) NOT NULL
);

CREATE INDEX ix_result_serial ON station_result (serial, op);
CREATE INDEX ix_genealogy_lot ON genealogy (lot);
CREATE INDEX ix_torque_op ON torque_result (op, result);
