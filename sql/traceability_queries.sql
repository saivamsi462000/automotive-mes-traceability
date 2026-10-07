-- name: unit_birth_history
-- Complete "birth history" of one serial: every station, component and torque result.
SELECT 'STATION' AS record, op, result, detail, ts FROM station_result WHERE serial = :serial
UNION ALL
SELECT 'COMPONENT', op, part_number, lot || ' / ' || component_serial, ts FROM genealogy WHERE serial = :serial
UNION ALL
SELECT 'TORQUE', op, result, 'bolt ' || bolt || ' try ' || attempt || ': ' || torque_nm || ' Nm, ' || angle_deg || ' deg', ts
FROM torque_result WHERE serial = :serial
ORDER BY ts;

-- name: containment_by_lot
-- Which finished units contain a suspect supplier lot, and where are they now?
SELECT g.lot, g.part_number, u.serial, u.variant, u.status, u.rack, u.rfid_epc
FROM genealogy g
JOIN unit u ON u.serial = g.serial
WHERE g.lot = :lot
ORDER BY u.rack, u.serial;

-- name: first_pass_yield_by_station
-- FPY = units passing a station on the first attempt / units processed at that station.
WITH first_try AS (
    SELECT serial, op, MIN(id) AS first_id
    FROM station_result
    WHERE op <> 'RW01' AND result IN ('OK', 'NOK')
    GROUP BY serial, op
)
SELECT f.op,
       COUNT(*)                                                  AS units,
       SUM(CASE WHEN s.result = 'OK' THEN 1 ELSE 0 END)          AS first_pass_ok,
       ROUND(1.0 * SUM(CASE WHEN s.result = 'OK' THEN 1 ELSE 0 END) / COUNT(*), 4) AS fpy
FROM first_try f
JOIN station_result s ON s.id = f.first_id
GROUP BY f.op
ORDER BY f.op;

-- name: torque_first_hit_rate
-- Share of bolts tightened OK on the first hit (a re-hit is allowed but signals tool/joint issues).
SELECT op,
       COUNT(*) AS first_hits,
       ROUND(1.0 * SUM(CASE WHEN result = 'OK' THEN 1 ELSE 0 END) / COUNT(*), 4) AS first_hit_ok_rate
FROM torque_result
WHERE attempt = 1
GROUP BY op;

-- name: open_nonconformances
SELECT nc_id, serial, op, description, opened_at FROM nonconformance WHERE status = 'OPEN';

-- name: nc_pareto
SELECT op, COUNT(*) AS ncs,
       SUM(CASE WHEN disposition = 'REWORK' THEN 1 ELSE 0 END) AS reworked,
       SUM(CASE WHEN disposition = 'SCRAP' THEN 1 ELSE 0 END)  AS scrapped
FROM nonconformance
GROUP BY op
ORDER BY ncs DESC;

-- name: scan_rejects
-- Error-proofing catches: wrong part, held lot or duplicate component blocked at scan.
SELECT op, detail, COUNT(*) AS occurrences
FROM station_result
WHERE result = 'SCAN_REJECT'
GROUP BY op, detail
ORDER BY occurrences DESC;
