# Functional Specification: Traceability & Error-Proofing Interlocks

| ID | Function | Rule | Implemented in | Test |
|---|---|---|---|---|
| F-01 | Serialization | Each knuckle gets a unique serial `FSMyymmddNNNNN` and an ISO/IEC 15434 DMC payload | `register_unit` | `test_serialization_is_unique_and_registered` |
| F-02 | Variant control | Only configured variants (STD, PERF) can be built | `register_unit` | `test_unknown_variant_rejected` |
| F-03 | Route enforcement | A station releases only if all previous ops are OK | `station_request` | `test_route_interlock_blocks_skipped_operation` |
| F-04 | No double processing | A completed op returns code 3 | `station_request` | `test_completed_operation_cannot_repeat` |
| F-05 | Part validation (poka-yoke) | Scanned part number must match the variant BOM | `scan_component` | `test_wrong_variant_part_rejected` |
| F-06 | Component uniqueness | A component serial can be consumed only once (DB UNIQUE) | `scan_component`, schema | `test_component_serial_cannot_be_used_twice` |
| F-07 | Press validation | Force 28–36 kN **and** depth 41.8–42.2 mm, otherwise NC | `record_press` | `test_rework_releases_unit_back_to_failed_operation` |
| F-08 | Torque validation | Torque **and** angle in window; 1 re-hit allowed, then NC | `record_torque` | `test_torque_retry_then_nonconformance`, `test_angle_out_of_window_is_nok_even_if_torque_ok` |
| F-09 | NC hold | NC sets the unit to NC_HOLD; every station blocks it (code 4) and an andon fires | `_raise_nc` | `test_torque_retry_then_nonconformance`, `test_nonconformance_raises_andon` |
| F-10 | Rework / scrap | Technician disposition; REWORK returns the unit to the failed op, SCRAP blocks it permanently | `rework` | `test_rework_releases_unit_back_to_failed_operation`, `test_scrap_disposition_blocks_unit` |
| F-11 | Pack & RFID | Rack assignment (12 per rack) and RFID EPC written to the unit | `pack` | `test_full_route_packs_unit_with_rfid` |
| F-12 | Lot containment | Holding a lot returns every affected serial and blocks further use (code 6) | `hold_lot` | `test_lot_containment_finds_units_and_blocks_new_use` |
| F-13 | PLC handshake | Release / reason code written to OPC UA tags | `mes/plc.py` | `test_plc_handshake_writes_release_and_reason` |
