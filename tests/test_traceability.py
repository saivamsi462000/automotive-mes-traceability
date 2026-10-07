import pytest

from mes.plc import REASON_CODES, TagServer, handshake, tag
from mes.traceability import TraceabilityMES


@pytest.fixture
def mes():
    return TraceabilityMES()


def ok_press(m, s):
    assert m.record_press(s, 32.0, 42.0)


def ok_torque(m, s, op, nm):
    for bolt in (1, 2):
        assert m.record_torque(s, op, bolt, nm, 40.0 if op == "OP30" else 30.0, 1) == "OK"
    m.complete_torque_op(s, op)


def test_serialization_is_unique_and_registered(mes):
    a, b = mes.register_unit("FSM-200-STD"), mes.register_unit("FSM-200-PERF")
    assert a != b and mes._unit(a)["status"] == "WIP"
    assert mes._unit(a)["dmc"].startswith("[)>06PFSM-200-STD")


def test_unknown_variant_rejected(mes):
    with pytest.raises(ValueError):
        mes.register_unit("FSM-999")


def test_route_interlock_blocks_skipped_operation(mes):
    s = mes.register_unit("FSM-200-STD")
    assert mes.station_request(s, "OP30") == (False, 2)
    assert mes.station_request(s, "OP20") == (True, 0)


def test_unknown_serial_blocked(mes):
    assert mes.station_request("FSM000", "OP20") == (False, 1)


def test_completed_operation_cannot_repeat(mes):
    s = mes.register_unit("FSM-200-STD")
    assert mes.station_request(s, "OP10") == (False, 3)


def test_wrong_variant_part_rejected(mes):
    s = mes.register_unit("FSM-200-STD")
    assert mes.scan_component(s, "OP40", "CAL-4410-P|L1|C1") == (False, 5)
    assert mes.scan_component(s, "OP40", "CAL-4410-S|L1|C1") == (True, 0)


def test_component_serial_cannot_be_used_twice(mes):
    a, b = mes.register_unit("FSM-200-STD"), mes.register_unit("FSM-200-STD")
    assert mes.scan_component(a, "OP20", "HB-7720|L1|B1")[0]
    assert mes.scan_component(b, "OP20", "HB-7720|L1|B1") == (False, 7)


def test_torque_retry_then_nonconformance(mes):
    s = mes.register_unit("FSM-200-STD")
    ok_press(mes, s)
    assert mes.record_torque(s, "OP30", 1, 90.0, 40, attempt=1) == "RETRY"
    assert mes.record_torque(s, "OP30", 1, 90.0, 40, attempt=2) == "NC"
    assert mes._unit(s)["status"] == "NC_HOLD"
    assert mes.station_request(s, "OP40") == (False, 4)


def test_angle_out_of_window_is_nok_even_if_torque_ok(mes):
    s = mes.register_unit("FSM-200-STD")
    assert mes.record_torque(s, "OP30", 1, 100.0, 75.0, attempt=1) == "RETRY"


def test_rework_releases_unit_back_to_failed_operation(mes):
    s = mes.register_unit("FSM-200-STD")
    assert not mes.record_press(s, 40.0, 42.0)
    mes.rework(s, "tech", "re-pressed")
    assert mes._unit(s)["status"] == "WIP"
    assert mes.station_request(s, "OP20") == (True, 0)


def test_scrap_disposition_blocks_unit(mes):
    s = mes.register_unit("FSM-200-STD")
    mes.record_press(s, 40.0, 42.0)
    mes.rework(s, "tech", "bearing damaged", "SCRAP")
    assert mes.station_request(s, "OP20") == (False, 8)


def test_full_route_packs_unit_with_rfid(mes):
    s = mes.register_unit("FSM-200-STD")
    mes.scan_component(s, "OP20", "HB-7720|L1|B1"); ok_press(mes, s)
    ok_torque(mes, s, "OP30", 100.0)
    mes.scan_component(s, "OP40", "CAL-4410-S|L2|C1"); ok_torque(mes, s, "OP40", 120.0)
    assert mes.record_inspection(s, {"visual": True})
    assert mes.pack(s) == "RACK-0001"
    u = mes._unit(s)
    assert u["status"] == "PACKED" and u["rfid_epc"].startswith("3034")


def test_lot_containment_finds_units_and_blocks_new_use(mes):
    a, b = mes.register_unit("FSM-200-STD"), mes.register_unit("FSM-200-STD")
    mes.scan_component(a, "OP40", "CAL-4410-S|L-BAD|C1")
    mes.scan_component(b, "OP40", "CAL-4410-S|L-OK|C2")
    assert mes.hold_lot("L-BAD", "supplier defect") == [a]
    c = mes.register_unit("FSM-200-STD")
    assert mes.scan_component(c, "OP40", "CAL-4410-S|L-BAD|C3") == (False, 6)


def test_plc_handshake_writes_release_and_reason(mes):
    plc = TagServer()
    s = mes.register_unit("FSM-200-STD")
    ok, reason = handshake(plc, mes, "OP30", s)
    assert not ok and reason == REASON_CODES[2]
    assert plc.read(tag("OP30", "MESRelease")) == 0 and plc.read(tag("OP30", "MESReasonCode")) == 2
    assert plc.node_id("OP30.MESRelease") == "ns=2;s=[Line1]OP30.MESRelease"


def test_nonconformance_raises_andon(mes):
    s = mes.register_unit("FSM-200-STD")
    mes.record_press(s, 20.0, 42.0)
    assert mes.con.execute("SELECT kind FROM andon_event").fetchone()[0] == "QUALITY"
