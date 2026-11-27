"""CPU checks for source-gated freight construction and original history."""
import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from freight_zone import CASES, build_case, measure_history, validate_site
from finalize_saved import finalize
from original_runner import construct
from delivery_audit import audit_attempt, audit_comparisons


def site(effective=True):
    return {
        "cell_id": "C386226", "layout": "one_way_road",
        "road": {"source_sha256": "road-source", "one_way_readback": True,
                 "approach_waypoints": [[0, 0], [1, 0]], "freight_entry_waypoint": [0, 1],
                 "freight_entry_source_sha256": "freight-entry"},
        "zone": {"designation": "freight_curb_loading", "marking_source_sha256": "mark",
                 "boundary_source_sha256": "boundary", "curb_adjacency_source_sha256": "curb",
                 "parking_pose_source_sha256": "pose", "polygon_xy": [[2, -2], [6, -2], [6, 2], [2, 2]],
                 "parking_pose": [4, 0], "materials_anchor": [4, 1], "passenger_anchor": [4, -1]},
        "clock": {"source_sha256": "clock", "civil_time_iso": "2026-11-26T12:00:00-08:00",
                  "timezone": "America/Los_Angeles"},
        "regulations": {"source_sha256": "provision", "effective_hours_source_sha256": "hours",
                        "jurisdiction": "source-reviewed Nevada authority", "effective_at_civil_time": effective},
        "vehicle_blueprint": "ego", "vehicle_blueprint_source_sha256": "ego-blueprint",
        "driver_responsibility_source_sha256": "driver-assignment",
        "materials_inventory": ["box-a"], "materials_inventory_source_sha256": "inventory",
        "freight_vehicle_blueprint": "truck", "freight_vehicle_blueprint_source_sha256": "truck-blueprint",
        "passenger_blueprint": "walker", "passenger_blueprint_source_sha256": "walker-blueprint",
        "activity_controller_source_sha256": "controller",
        "traffic_and_official_directions_source_sha256": "traffic-and-directions",
    }


class Adapter:
    def __init__(self):
        self.calls = []
        self.count = 0

    def _actor(self, method, *args, **kwargs):
        self.count += 1
        actor = f"actor-{self.count}"
        self.calls.append((method, args, kwargs))
        return actor

    def spawn_vehicle(self, *args, **kwargs):
        return self._actor("spawn_vehicle", *args, **kwargs)

    def spawn_materials(self, *args, **kwargs):
        return self._actor("spawn_materials", *args, **kwargs)

    def spawn_passenger(self, *args, **kwargs):
        return self._actor("spawn_passenger", *args, **kwargs)

    def set_route(self, *args, **kwargs):
        self.calls.append(("set_route", args, kwargs))

    def set_conduct(self, *args, **kwargs):
        self.calls.append(("set_conduct", args, kwargs))

    def set_material_action(self, *args, **kwargs):
        self.calls.append(("set_material_action", args, kwargs))

    def set_passenger_action(self, *args, **kwargs):
        self.calls.append(("set_passenger_action", args, kwargs))

    def set_freight_arrival(self, *args, **kwargs):
        self.calls.append(("set_freight_arrival", args, kwargs))

    def destroy(self, actor):
        self.calls.append(("destroy", (actor,), {}))


def rows(case):
    result = []
    for index in range(900):
        row = {"case_id": case.name, "original_frame": 1000 + index,
               "elapsed_s": index / 20, "ego_id": "ego-1", "driver_id": "driver-1", "materials_id": "materials-1",
               "passenger_id": "passenger-1", "freight_vehicle_id": "freight-1",
               "map_sha256": "map", "zone_source_sha256": "zone",
               "regulations_source_sha256": "regulation", "clock_source_sha256": "clock",
               "camera_plan_sha256": "four-camera-plan",
               "source_sha256": "original-frame", "control_source_sha256": "control",
               "traffic_and_official_directions_source_sha256": "traffic-and-directions",
               "ego_center_xy": [4, 0] if index >= 40 else [1, 0],
               "ego_speed_mps": 0 if index >= 40 else 5,
               "freight_center_xy": [0, 1], "freight_entry_blocked": False,
               "material_event": None, "passenger_event": None, "freight_event": None}
        if case.material_action == "pickup_load":
            if index == 60:
                row.update(material_event="pickup_started", material_event_source_sha256="inventory-trace")
            if index == 90:
                row.update(material_event="loading_started", material_event_source_sha256="inventory-trace")
            if index == 180:
                row.update(material_event="loading_completed", material_event_source_sha256="inventory-trace")
        if case.material_action == "unload_deliver":
            if index == 60:
                row.update(material_event="unloading_started", material_event_source_sha256="inventory-trace")
            if index == 180:
                row.update(material_event="delivery_completed", material_event_source_sha256="inventory-trace")
        if case.passenger_action == "board" and index == 60:
            row.update(passenger_event="boarding_started", passenger_event_source_sha256="passenger-trace")
        if case.passenger_action == "alight" and index == 60:
            row.update(passenger_event="alighting_started", passenger_event_source_sha256="passenger-trace")
        if case.freight_arrival != "none" and index == 50:
            row.update(freight_event="waiting_to_enter" if case.freight_arrival == "waiting" else "about_to_enter",
                       freight_event_source_sha256="freight-trace")
        result.append(row)
    return result


class FreightZoneTest(unittest.TestCase):
    def test_all_case_controls_and_source_gates(self):
        for case in CASES:
            with self.subTest(case=case.name):
                local_site = site(case.hours == "effective")
                adapter = Adapter()
                built = build_case(adapter, local_site, case)
                self.assertEqual(len(built["owned"]), 4)
                self.assertEqual([x[0] for x in adapter.calls[:4]],
                                 ["spawn_vehicle", "spawn_materials", "spawn_passenger", "spawn_vehicle"])
                self.assertIn(("set_material_action", (built["materials"], built["ego"], case.material_action),
                               {"delay_s": case.activity_delay_s}), adapter.calls)
                self.assertIn(("set_freight_arrival", (built["freight"], case.freight_arrival, [0, 1]), {}), adapter.calls)
                observed = measure_history(rows(case), case, local_site)
                self.assertEqual(observed["frame_count"], 900)
                self.assertGreater(observed["in_zone_halted_frame_count"], 0)
                self.assertEqual(observed["legal_judgment"], "unresolved")

    def test_missing_source_rejected_before_spawn(self):
        case = CASES[3]
        local_site = site()
        local_site["zone"]["marking_source_sha256"] = ""
        adapter = Adapter()
        with self.assertRaisesRegex(ValueError, "freight zone source"):
            build_case(adapter, local_site, case)
        self.assertEqual(adapter.calls, [])

    def test_wrong_hours_rejected(self):
        with self.assertRaisesRegex(ValueError, "effective-hours"):
            validate_site(site(False), CASES[3])

    def test_original_frame_and_event_source_rejected(self):
        case = CASES[3]
        original = rows(case)
        broken = copy.deepcopy(original)
        broken[60]["original_frame"] += 1
        with self.assertRaisesRegex(ValueError, "case/frame join"):
            measure_history(broken, case, site())
        broken = copy.deepcopy(original)
        broken[60].pop("material_event_source_sha256")
        with self.assertRaisesRegex(ValueError, "material_event source"):
            measure_history(broken, case, site())

    def test_reviewed_original_source_and_saved_seal(self):
        case = CASES[3]
        local_site = site()
        local_site.update(source_kind="reviewed_original_site", reviewer="local original source reviewer")
        local_site["zone"]["boundary_source_sha256"] = "zone"
        local_site["regulations"]["source_sha256"] = "regulation"
        aid = Path(__file__).resolve().parents[1].name
        exact = aid + "__" + case.name
        scratch = Path.cwd() / ".runtime-work" / "c386226-5071-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            root = Path(temporary)
            site_path = root / "site-context.json"
            site_path.write_text(json.dumps(local_site) + "\n")
            site_sha = hashlib.sha256(site_path.read_bytes()).hexdigest()
            manifest = {"source_kind": "reviewed_original_site", "diagnostic_fixture": False,
                        "reviewer": "local original source reviewer", "case_id": exact,
                        "source_provenance": {"kind": "original_reviewed_site", "diagnostic_fixture": False,
                                              "reviewer": "local original source reviewer", "citation": "reviewed site record"},
                        "files": {"site-context.json": {"sha256": site_sha}}}
            manifest_path = root / "source-manifest.json"
            manifest_path.write_text(json.dumps(manifest) + "\n")
            built = construct(Adapter(), manifest_path, site_path, exact)
            self.assertEqual(built["case_id"], exact)
            bad = dict(manifest)
            bad["diagnostic_fixture"] = True
            manifest_path.write_text(json.dumps(bad) + "\n")
            with self.assertRaisesRegex(ValueError, "reviewed original freight source"):
                construct(Adapter(), manifest_path, site_path, exact)
            history_path = root / "history.jsonl"
            history_path.write_text("".join(json.dumps(row) + "\n" for row in rows(case)))
            seal_path = root / "capture-seal.json"
            seal_path.write_text(json.dumps({"case_id": case.name, "site_sha256": site_sha,
                "original_history_sha256": hashlib.sha256(history_path.read_bytes()).hexdigest()}) + "\n")
            result = finalize(history_path, site_path, seal_path, root / "measured.json")
            self.assertEqual(result["measurement"]["material_events"][0]["event"], "pickup_started")
            self.assertFalse(result["physical_visibility_verified"])
            broken = rows(case)
            broken[60]["material_event_source_sha256"] = ""
            history_path.write_text("".join(json.dumps(row) + "\n" for row in broken))
            seal_path.write_text(json.dumps({"case_id": case.name, "site_sha256": site_sha,
                "original_history_sha256": hashlib.sha256(history_path.read_bytes()).hexdigest()}) + "\n")
            with self.assertRaisesRegex(ValueError, "material_event source"):
                finalize(history_path, site_path, seal_path, root / "rejected.json")

    def test_independent_audit_rejects_missing_original_attempt(self):
        scratch = Path.cwd() / ".runtime-work" / "c386226-5071-tests" / "never-created-attempt"
        aid = Path(__file__).resolve().parents[1].name
        with self.assertRaisesRegex(ValueError, "original attempt missing"):
            audit_attempt(scratch, aid + "__" + CASES[0].name)

    def test_comparison_rejects_fixed_source_change(self):
        aid = Path(__file__).resolve().parents[1].name
        reports = {}
        fixed = {"road_source_sha256": "road", "zone_source_sha256": "zone",
                 "regulations_source_sha256": "regulation", "effective_hours_source_sha256": "hours",
                 "camera_plan_sha256": "camera", "vehicle_blueprint": "car",
                 "passenger_blueprint": "passenger", "freight_vehicle_blueprint": "truck",
                 "materials_inventory_source_sha256": "inventory",
                 "freight_entry_source_sha256": "freight-entry",
                 "traffic_and_official_directions_source_sha256": "traffic",
                 "clock_source_sha256": "clock", "civil_time_iso": "2026-11-26T12:00:00-08:00"}
        for c in CASES:
            cid = aid + "__" + c.name
            report = {"format": "c386226-independent-original-audit-v1", "case_id": cid,
                      "source_kind": "original_native_capture", "legal_status": "unresolved",
                      "physical_acceptance": False,
                      "comparison_record": {"case_id": cid, "frame_count": 900,
                          "original_history_sha256": "history-" + c.name,
                          "site_sha256": "site-" + c.name, **fixed,
                          "conduct": c.conduct, "material_action": c.material_action,
                          "activity_delay_s": c.activity_delay_s,
                          "passenger_action": c.passenger_action,
                          "freight_arrival": c.freight_arrival,
                          "regulations_effective": c.hours == "effective",
                          "material_events": [c.material_action] if c.material_action != "none" else [],
                          "halt_to_material_event_s": c.activity_delay_s if c.material_action != "none" else None,
                          "passenger_events": [c.passenger_action] if c.passenger_action != "none" else [],
                          "freight_events": [c.freight_arrival] if c.freight_arrival != "none" else []}}
            if c.hours != "effective":
                report["comparison_record"]["civil_time_iso"] = "2026-11-26T03:00:00-08:00"
            reports[cid] = report
        passed = audit_comparisons(reports)
        self.assertEqual(len(passed), 6)
        broken = copy.deepcopy(reports)
        broken[aid + "__stand_no_material"]["comparison_record"]["road_source_sha256"] = "changed-road"
        with self.assertRaisesRegex(ValueError, "fixed comparison condition changed"):
            audit_comparisons(broken)


if __name__ == "__main__":
    unittest.main()
