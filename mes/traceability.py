"""Discrete-manufacturing MES core: serialization, routing interlocks, part validation,
torque/press validation, non-conformance and rework, genealogy and andon.

All state lives in SQL (see sql/schema.sql) as it would in a FactoryTalk or Ignition
based MES. Station results are written transactionally, so the database is always
the single source of truth for traceability.
"""
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class TraceabilityMES:
    def __init__(self, route_path: str | Path = ROOT / "config/route_FSM-200.json",
                 db: str = ":memory:", clock: datetime | None = None):
        self.route = json.loads(Path(route_path).read_text())
        self.ops = [s["op"] for s in self.route["stations"]]
        self.stations = {s["op"]: s for s in self.route["stations"]}
        self.con = sqlite3.connect(db)
        self.con.row_factory = sqlite3.Row
        self.con.executescript((ROOT / "sql/schema.sql").read_text())
        self.clock = clock or datetime(2022, 3, 7, 6, 0, 0)
        self._seq = 0

    # ----------------------------------------------------------------- utils
    def now(self, advance_s: float = 0) -> str:
        self.clock += timedelta(seconds=advance_s)
        return self.clock.isoformat(timespec="seconds")

    def _unit(self, serial: str):
        return self.con.execute("SELECT * FROM unit WHERE serial = ?", (serial,)).fetchone()

    def _passed_ops(self, serial: str) -> set[str]:
        rows = self.con.execute(
            "SELECT op FROM station_result WHERE serial = ? AND result = 'OK'", (serial,)).fetchall()
        return {r["op"] for r in rows}

    def _log_result(self, serial, op, result, detail=""):
        self.con.execute("INSERT INTO station_result (serial, op, result, detail, ts) VALUES (?,?,?,?,?)",
                         (serial, op, result, detail, self.now(1)))

    # ---------------------------------------------------------- serialization
    def register_unit(self, variant: str) -> str:
        if variant not in self.route["variants"]:
            raise ValueError(f"Unknown variant {variant}")
        self._seq += 1
        serial = f"{self.route['serial_prefix']}{self.clock:%y%m%d}{self._seq:05d}"
        dmc = f"[)>06P{variant}S{serial}"  # ISO/IEC 15434 style data-matrix payload
        self.con.execute("INSERT INTO unit (serial, variant, dmc, status, created_at) VALUES (?,?,?,?,?)",
                         (serial, variant, dmc, "WIP", self.now(2)))
        self._log_result(serial, "OP10", "OK", "serialized")
        return serial

    # --------------------------------------------------------- route interlock
    def station_request(self, serial: str, op: str) -> tuple[bool, int]:
        """Interlock decision returned to the PLC: (release?, reason code)."""
        unit = self._unit(serial)
        if unit is None:
            return False, 1
        if unit["status"] == "SCRAP":
            return False, 8
        if unit["status"] == "NC_HOLD":
            return False, 4
        passed = self._passed_ops(serial)
        if op in passed:
            return False, 3
        idx = self.ops.index(op)
        if any(prev not in passed for prev in self.ops[:idx]):
            return False, 2
        return True, 0

    # ------------------------------------------------------ part validation
    def scan_component(self, serial: str, op: str, barcode: str) -> tuple[bool, int]:
        """Barcode format: <part_number>|<lot>|<component_serial>."""
        part_no, lot, comp_sn = barcode.split("|")
        kind = self.stations[op]["scan_component"]
        expected = self.route["variants"][self._unit(serial)["variant"]][kind]
        if part_no != expected:
            self._log_result(serial, op, "SCAN_REJECT", f"expected {expected}, scanned {part_no}")
            return False, 5
        if self.con.execute("SELECT 1 FROM lot_hold WHERE lot = ? AND released_at IS NULL", (lot,)).fetchone():
            self._log_result(serial, op, "SCAN_REJECT", f"lot {lot} on hold")
            return False, 6
        if self.con.execute("SELECT 1 FROM genealogy WHERE component_serial = ?", (comp_sn,)).fetchone():
            self._log_result(serial, op, "SCAN_REJECT", f"component {comp_sn} already consumed")
            return False, 7
        self.con.execute("INSERT INTO genealogy (serial, op, component_type, part_number, lot, component_serial, ts) "
                         "VALUES (?,?,?,?,?,?,?)", (serial, op, kind, part_no, lot, comp_sn, self.now(3)))
        return True, 0

    # --------------------------------------------------------- process data
    def record_press(self, serial: str, force_kn: float, depth_mm: float) -> bool:
        spec = self.stations["OP20"]
        ok = (spec["press_force_kn"]["low"] <= force_kn <= spec["press_force_kn"]["high"]
              and spec["press_depth_mm"]["low"] <= depth_mm <= spec["press_depth_mm"]["high"])
        self.con.execute("INSERT INTO press_result (serial, force_kn, depth_mm, result, ts) VALUES (?,?,?,?,?)",
                         (serial, force_kn, depth_mm, "OK" if ok else "NOK", self.now(25)))
        if ok:
            self._log_result(serial, "OP20", "OK")
        else:
            self._raise_nc(serial, "OP20", f"press force {force_kn} kN / depth {depth_mm} mm out of window")
        return ok

    def record_torque(self, serial: str, op: str, bolt: int, torque: float, angle: float, attempt: int) -> str:
        """Returns OK, RETRY (re-hit allowed) or NC (retries exhausted -> non-conformance)."""
        spec = self.stations[op]
        t, a = spec["torque_nm"], spec["angle_deg"]
        ok = t["low"] <= torque <= t["high"] and a["low"] <= angle <= a["high"]
        self.con.execute("INSERT INTO torque_result (serial, op, bolt, attempt, torque_nm, angle_deg, result, ts) "
                         "VALUES (?,?,?,?,?,?,?,?)",
                         (serial, op, bolt, attempt, torque, angle, "OK" if ok else "NOK", self.now(6)))
        if ok:
            return "OK"
        if attempt <= spec["max_retries"]:
            return "RETRY"
        self._raise_nc(serial, op, f"bolt {bolt}: {torque} Nm / {angle}° out of window after {attempt} attempts")
        return "NC"

    def complete_torque_op(self, serial: str, op: str) -> None:
        self._log_result(serial, op, "OK", f"{self.stations[op]['bolts']} bolts OK")

    def record_inspection(self, serial: str, checks: dict[str, bool]) -> bool:
        failed = [k for k, v in checks.items() if not v]
        if failed:
            self._raise_nc(serial, "OP50", "failed: " + ", ".join(failed))
            return False
        self._log_result(serial, "OP50", "OK")
        return True

    def pack(self, serial: str) -> str:
        cap = self.stations["OP60"]["rack_capacity"]
        packed = self.con.execute("SELECT COUNT(*) FROM unit WHERE status = 'PACKED'").fetchone()[0]
        rack = f"RACK-{packed // cap + 1:04d}"
        epc = f"3034{int(serial[-5:]):020X}"  # simplified SGTIN-96 style EPC
        self.con.execute("UPDATE unit SET status = 'PACKED', rack = ?, rfid_epc = ? WHERE serial = ?",
                         (rack, epc, serial))
        self._log_result(serial, "OP60", "OK", rack)
        return rack

    # ---------------------------------------------- non-conformance & rework
    def _raise_nc(self, serial, op, description):
        self.con.execute("INSERT INTO nonconformance (serial, op, description, status, opened_at) "
                         "VALUES (?,?,?,?,?)", (serial, op, description, "OPEN", self.now(1)))
        self.con.execute("UPDATE unit SET status = 'NC_HOLD' WHERE serial = ?", (serial,))
        self._log_result(serial, op, "NOK", description)
        self.andon(op, "QUALITY", description)

    def rework(self, serial: str, technician: str, action: str, disposition: str = "REWORK") -> None:
        nc = self.con.execute("SELECT * FROM nonconformance WHERE serial = ? AND status = 'OPEN'",
                              (serial,)).fetchone()
        if nc is None:
            raise ValueError(f"No open NC for {serial}")
        self.con.execute("UPDATE nonconformance SET status = 'CLOSED', disposition = ?, action = ?, "
                         "closed_by = ?, closed_at = ? WHERE nc_id = ?",
                         (disposition, action, technician, self.now(300), nc["nc_id"]))
        new_status = "SCRAP" if disposition == "SCRAP" else "WIP"
        self.con.execute("UPDATE unit SET status = ? WHERE serial = ?", (new_status, serial))
        self._log_result(serial, "RW01", disposition, action)

    def andon(self, op: str, kind: str, message: str) -> None:
        self.con.execute("INSERT INTO andon_event (op, kind, message, ts) VALUES (?,?,?,?)",
                         (op, kind, message, self.now()))

    # ----------------------------------------------------------- containment
    def hold_lot(self, lot: str, reason: str) -> list[str]:
        """Supplier lot containment: block further use and return every affected unit."""
        self.con.execute("INSERT INTO lot_hold (lot, reason, held_at) VALUES (?,?,?)", (lot, reason, self.now()))
        rows = self.con.execute("SELECT DISTINCT serial FROM genealogy WHERE lot = ?", (lot,)).fetchall()
        return [r["serial"] for r in rows]
