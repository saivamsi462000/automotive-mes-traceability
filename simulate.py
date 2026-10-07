"""Simulate one production week on the FSM-200 line and produce traceability evidence.

Usage:
    python simulate.py --units 600
Writes KPIs, figures, a containment report and an example birth history to ./output/.
"""
import argparse
import csv
import json
import random
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from mes.plc import TagServer, handshake, tag
from mes.traceability import ROOT, TraceabilityMES

OUT = ROOT / "output"
SUSPECT_LOT = "L-CAL-2207"


def queries() -> dict[str, str]:
    text = (ROOT / "sql/traceability_queries.sql").read_text()
    parts = re.split(r"^-- name: (\w+)\s*$", text, flags=re.M)
    return {parts[i]: parts[i + 1].strip().rstrip(";") for i in range(1, len(parts), 2)}


def caliper_lot(i: int) -> str:
    return ["L-CAL-2205", "L-CAL-2206", SUSPECT_LOT, "L-CAL-2208"][min(i // 150, 3)]


def run_torque(mes, plc, rng, serial, op, bias=0.0):
    spec = mes.stations[op]["torque_nm"]
    for bolt in range(1, mes.stations[op]["bolts"] + 1):
        attempt = 1
        while True:
            # Most hits are centred on target; a few are under-torqued (cross-thread / tool issue)
            torque = rng.gauss(spec["target"] + bias, 1.6)
            if rng.random() < 0.012:
                torque = spec["low"] - rng.uniform(1, 6)
            angle = rng.gauss(42 if op == "OP30" else 34, 4)
            plc.write(tag(op, f"Bolt{bolt}.Torque"), round(torque, 1))
            plc.write(tag(op, f"Bolt{bolt}.Angle"), round(angle, 1))
            status = mes.record_torque(serial, op, bolt, round(torque, 1), round(angle, 1), attempt)
            if status == "OK":
                break
            if status == "NC":
                return False
            attempt += 1
    mes.complete_torque_op(serial, op)
    return True


def build_unit(mes, plc, rng, i, serial=None):
    """Drive one unit through the route; returns serial and whether it ended in NC hold."""
    if serial is None:
        variant = "FSM-200-PERF" if rng.random() < 0.3 else "FSM-200-STD"
        serial = mes.register_unit(variant)
    variant = mes._unit(serial)["variant"]

    for op in mes.ops[1:]:
        ok, reason = handshake(plc, mes, op, serial)
        if not ok:
            if reason == "Operation already complete":
                continue
            return serial, reason
        st = mes.stations[op]
        if "scan_component" in st and not mes.con.execute(
                "SELECT 1 FROM genealogy WHERE serial = ? AND op = ?", (serial, op)).fetchone():
            kind = st["scan_component"]
            pn = mes.route["variants"][variant][kind]
            if kind == "caliper" and rng.random() < 0.01:   # operator grabs the wrong variant caliper
                wrong = "CAL-4410-P" if pn.endswith("S") else "CAL-4410-S"
                mes.scan_component(serial, op, f"{wrong}|{caliper_lot(i)}|X{i:06d}")
                mes.andon(op, "MATERIAL", "wrong caliper variant presented")
            lot = caliper_lot(i) if kind == "caliper" else f"L-HB-{2100 + i // 200}"
            ok, code = mes.scan_component(serial, op, f"{pn}|{lot}|{kind[:3].upper()}{i:06d}")
            if not ok:
                return serial, f"scan blocked ({code})"
        if st["type"] == "press":
            force = rng.gauss(32, 1.4)
            depth = rng.gauss(42.0, 0.05)
            if rng.random() < 0.006:
                depth = 42.0 + rng.choice([-1, 1]) * rng.uniform(0.25, 0.4)
            if not mes.record_press(serial, round(force, 2), round(depth, 3)):
                return serial, "NC"
        elif st["type"] == "torque":
            if not run_torque(mes, plc, rng, serial, op):
                return serial, "NC"
        elif st["type"] == "inspection":
            if not mes.record_inspection(serial, {"visual": rng.random() > 0.004,
                                                  "caliper_orientation": True, "dmc_readable": True}):
                return serial, "NC"
        elif st["type"] == "pack":
            mes.pack(serial)
        mes.now(rng.uniform(40, 55))  # cycle time between stations
    return serial, "PACKED"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--units", type=int, default=600)
    ap.add_argument("--seed", type=int, default=11)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    mes, plc = TraceabilityMES(), TagServer()
    OUT.mkdir(exist_ok=True); (OUT / "figures").mkdir(exist_ok=True)

    outcomes = {}
    for i in range(args.units):
        serial, outcome = build_unit(mes, plc, rng, i)
        if outcome == "NC":
            nc = mes.con.execute("SELECT op FROM nonconformance WHERE serial = ? AND status = 'OPEN'",
                                 (serial,)).fetchone()
            scrap = nc["op"] == "OP20" and rng.random() < 0.5   # mis-pressed bearings are often scrapped
            mes.rework(serial, "tech.rw01", "re-pressed" if nc["op"] == "OP20" else
                       "bolt replaced and re-torqued" if nc["op"] in ("OP30", "OP40") else "cosmetic rework",
                       "SCRAP" if scrap else "REWORK")
            if not scrap:
                serial, outcome = build_unit(mes, plc, rng, i, serial)
                outcome = "PACKED_AFTER_REWORK" if outcome == "PACKED" else outcome
            else:
                outcome = "SCRAP"
        outcomes[serial] = outcome
        if i in (120, 380):
            mes.andon("OP30", "MAINTENANCE", "nutrunner socket worn - replaced")

    # Supplier notifies a caliper lot issue after the week's production
    affected = mes.hold_lot(SUSPECT_LOT, "Supplier 8D: caliper piston seal defect")
    q = queries()
    containment = mes.con.execute(q["containment_by_lot"], {"lot": SUSPECT_LOT}).fetchall()
    with open(OUT / "containment_report.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(containment[0].keys())
        w.writerows([tuple(r) for r in containment])

    # A unit built after the hold must be blocked at the caliper scan
    blocked_serial = mes.register_unit("FSM-200-STD")
    blocked = mes.scan_component(blocked_serial, "OP40", f"CAL-4410-S|{SUSPECT_LOT}|CALHOLD01")

    fpy = [dict(r) for r in mes.con.execute(q["first_pass_yield_by_station"])]
    rty = 1.0
    for r in fpy:
        rty *= r["fpy"]
    counts = {k: sum(1 for v in outcomes.values() if v == k) for k in set(outcomes.values())}
    kpis = {
        "units_started": args.units,
        "outcomes": counts,
        "first_pass_yield_by_station": fpy,
        "rolled_throughput_yield": round(rty, 4),
        "torque_first_hit": [dict(r) for r in mes.con.execute(q["torque_first_hit_rate"])],
        "nonconformance_pareto": [dict(r) for r in mes.con.execute(q["nc_pareto"])],
        "error_proofing_scan_rejects": [dict(r) for r in mes.con.execute(q["scan_rejects"])],
        "andon_events": mes.con.execute("SELECT COUNT(*) FROM andon_event").fetchone()[0],
        "containment": {"lot": SUSPECT_LOT, "affected_units": len(affected),
                        "racks": sorted({r["rack"] for r in containment if r["rack"]}),
                        "new_use_blocked": blocked == (False, 6)},
        "open_nonconformances": len(mes.con.execute(q["open_nonconformances"]).fetchall()),
    }
    (OUT / "kpi_summary.json").write_text(json.dumps(kpis, indent=2))

    example = next(s for s, o in outcomes.items() if o == "PACKED_AFTER_REWORK")
    hist = mes.con.execute(q["unit_birth_history"], {"serial": example}).fetchall()
    lines = [f"# Birth history — {example}", "", "| Record | Op | Result | Detail | Timestamp |", "|---|---|---|---|---|"]
    lines += [f"| {r[0]} | {r[1]} | {r[2]} | {r[3] or ''} | {r[4]} |" for r in hist]
    (OUT / "birth_history_example.md").write_text("\n".join(lines) + "\n")
    (OUT / "opcua_tag_snapshot.json").write_text(json.dumps(
        {plc.node_id(k): v for k, v in sorted(plc.tags.items())}, indent=2))

    # Figures
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar([r["op"] for r in fpy], [r["fpy"] for r in fpy], color="#2b6cb0")
    for i, r in enumerate(fpy):
        ax.text(i, r["fpy"] + 0.002, f"{r['fpy']:.1%}", ha="center", fontsize=9)
    ax.set_ylim(0.95, 1.005); ax.set_title(f"First-pass yield by station (RTY {rty:.1%})")
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    fig.tight_layout(); fig.savefig(OUT / "figures/fpy_by_station.png", dpi=150); plt.close(fig)

    for op in ["OP30", "OP40"]:
        vals = [r[0] for r in mes.con.execute("SELECT torque_nm FROM torque_result WHERE op = ?", (op,))]
        spec = mes.stations[op]["torque_nm"]
        fig, ax = plt.subplots(figsize=(7, 4))
        ax.hist(vals, bins=50, color="#4a5568")
        for k, c in [("low", "#c53030"), ("high", "#c53030"), ("target", "#2f855a")]:
            ax.axvline(spec[k], color=c, ls="--", label=f"{k} {spec[k]} Nm")
        ax.set_xlabel("Final torque (Nm)"); ax.set_ylabel("Tightenings"); ax.legend()
        ax.set_title(f"{op} {mes.stations[op]['name']}: torque distribution")
        fig.tight_layout(); fig.savefig(OUT / f"figures/torque_{op}.png", dpi=150); plt.close(fig)

    print(json.dumps({k: kpis[k] for k in ["outcomes", "rolled_throughput_yield", "containment",
                                           "open_nonconformances", "andon_events"]}, indent=2))
    print("FPY:", {r["op"]: r["fpy"] for r in fpy})
    print(f"Example birth history: {example}")


if __name__ == "__main__":
    main()
