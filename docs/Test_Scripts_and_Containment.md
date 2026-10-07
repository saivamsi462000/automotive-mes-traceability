# MES Test Scripts & Containment Procedure

## Part A: Site Acceptance Test scripts (excerpt)

| TS | Step | Expected | Pass/Fail |
|---|---|---|---|
| TS-01 | Load a knuckle at OP10 and trigger marking | Serial created; DMC grade ≥ B; unit in `unit` table as WIP | |
| TS-02 | Bypass OP20 and present the unit at OP30 | OP30 blocked, reason 2 shown on HMI | |
| TS-03 | Scan a PERF caliper on an STD unit at OP40 | Blocked, reason 5; `SCAN_REJECT` row logged | |
| TS-04 | Scan the same bearing label on two units | Second scan blocked, reason 7 | |
| TS-05 | Under-torque bolt 1 at OP30 (adjust controller program) | First hit NOK → re-hit allowed; second NOK → NC_HOLD, quality andon | |
| TS-06 | Present an NC_HOLD unit at OP40 | Blocked, reason 4 | |
| TS-07 | Disposition the unit as REWORK at RW01 | NC closed; unit returns to the failed op only | |
| TS-08 | Disposition as SCRAP | Every station blocks with reason 8 | |
| TS-09 | Complete a unit to OP60 | Rack assigned; RFID EPC written and read back | |
| TS-10 | Put a caliper lot on hold | Containment list generated; further scans blocked with reason 6 | |
| TS-11 | Pull the network cable to the MES for 60 s | PLC times out → no release (fail-safe); recovers when the network returns | |

Automated equivalents: `pytest -v` (15 tests).

## Part B: Supplier lot containment procedure

**Trigger:** supplier notification, field complaint or internal failure linked to a component lot.

1. **Hold the lot** in MES (Traceability search → Lot → *Hold*). New use is blocked immediately at every scan station.
2. **Run the containment query** `containment_by_lot` to list affected serials with status, rack and RFID EPC.
3. **Segregate**:
   - WIP units → divert to RW01 (status NC_HOLD)
   - Packed racks in the plant → red-tag and quarantine using the rack list
   - Shipped racks → notify the customer with the serial/RFID list
4. **Disposition** each unit (replace the component and re-test, or scrap). Every action is logged in `nonconformance`.
5. **Release the lot hold** only after the supplier 8D is closed and quality approves.

**Simulation evidence:** lot `L-CAL-2207` → **148 units in 14 racks** identified in one query (`output/containment_report.csv`). A new scan of the held lot was blocked.
