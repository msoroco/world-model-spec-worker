"""Exercise physical construction calls and source failures for the selected branch."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from curb_construction import execute, plan


class Adapter:
    def __init__(self):
        self.calls = []

    def spawn_vehicle(self, spec):
        self.calls.append(("spawn", spec))
        return spec["identity"]

    def configure_route(self, actor, route):
        self.calls.append(("route", actor, route))

    def configure_flashing_lights(self, actor, lights):
        self.calls.append(("lights", actor, lights))

    def configure_unit_movement(self, actor, movement):
        self.calls.append(("movement", actor, movement))

    def configure_shoulder_sign(self, source):
        self.calls.append(("sign", source["permitted_class"]))

    def configure_subject_position(self, actor, position):
        self.calls.append(("position", actor, position))

    def configure_officer_direction(self, source):
        self.calls.append(("officer", source))


def inputs():
    case = dict(case_id="example", edge_type="curb", parallel_request="parallel",
                closeness_request="nearest_feasible", intersection_request="outside_intersection",
                subject_position_request="roadway", sign_permitted_class="none",
                unit_class="authorized_emergency", light_request="qualified_active",
                immediate_request=True, officer_direction_request="none",
                approach_direction="opposing")
    site = dict(source_kind="native_map_readback", road_type="paved_highway",
                highway_dedication_source="map", public_access_source="map",
                highway_boundary_source="map", ego_route_id="ego", unit_route_id="unit",
                curb_or_edge_geometry_source="map", intersection_geometry_source="map",
                shoulder_boundary_source="map", ego_route_connected=True,
                unit_route_connected=True, unit_route_approaches_ego=True,
                unit_route_direction="opposing", selected_edge_type="curb",
                curb_readback=True, paved_shoulder_readback=True,
                roadway_shoulder_distinct=True, intersection_readback=True,
                position_region="outside_intersection")
    actors = dict(source_kind="native_blueprint_readback", ego_blueprint_id="vehicle.ego",
                  unit_blueprint_id="vehicle.unit", ego_driver_control_source="controller",
                  ego_vehicle_class="ordinary_motor_vehicle", unit_class="authorized_emergency")
    authority = dict(class_="authorized_emergency", authorization_source="record",
                     light_rule_source="rule", equipment_source="blueprint",
                     front_red_lamp_source="review", siren_equipment_source="review",
                     officer_context_source="review", siren_equipment_verified=True,
                     front_visible_red_lamp_verified=True,
                     qualifying_flashing_equipment_verified=True)
    authority["class"] = authority.pop("class_")
    shoulder = dict(source_kind="reviewed_sign_and_shoulder_readback",
                    shoulder_paving_source="map", sign_location_source="map",
                    sign_content_source="review", lawful_placement_source="review",
                    traffic_conflict_source="review", permitted_class="none",
                    lawfully_placed=False, sign_applies_to_segment=False,
                    edge_distance_target_m=0.3, body_yaw_target_deg=0.0,
                    position_request="roadway", parallel_request="parallel",
                    closeness_request="nearest_feasible")
    return case, site, actors, authority, shoulder


class ConstructionTest(unittest.TestCase):
    def test_curb_and_six_signed_classes_issue_distinct_geometry_calls(self):
        for signed_class in ("authorized_emergency", "permitted_emergency",
                             "traffic_incident_management", "tow_car",
                             "coroner_vehicle", "public_transit_bus"):
            case, site, actors, authority, shoulder = inputs()
            case["subject_position_request"] = "paved_shoulder_stop"
            case["sign_permitted_class"] = signed_class
            shoulder.update(position_request="paved_shoulder_stop", permitted_class=signed_class,
                            lawfully_placed=True, sign_applies_to_segment=True)
            adapter = Adapter()
            execute(adapter, case, site, actors, authority, shoulder)
            self.assertEqual([call[0] for call in adapter.calls],
                             ["spawn", "spawn", "route", "route", "lights",
                              "movement", "sign", "position"])
            self.assertEqual(adapter.calls[-1][2]["region"], "paved_shoulder_stop")
            self.assertEqual(adapter.calls[-1][2]["sign_permitted_class"], signed_class)

    def test_curb_officer_and_alternate_route(self):
        case, site, actors, authority, shoulder = inputs()
        case["officer_direction_request"] = "contrary_direction"
        authority["officer_direction_source"] = "officer.record"
        site.update(alternate_unit_route_id="alternate", alternate_unit_route_connected=True,
                    alternate_unit_route_direction="opposing",
                    alternate_unit_route_approaches_ego=True)
        adapter = Adapter()
        execute(adapter, case, site, actors, authority, shoulder,
                {"alternate_unit_route": True})
        self.assertIn(("route", "unit", "alternate"), adapter.calls)
        self.assertEqual(adapter.calls[-1], ("officer", "officer.record"))

    def test_missing_geometry_and_sign_are_rejected(self):
        case, site, actors, authority, shoulder = inputs()
        site["roadway_shoulder_distinct"] = False
        with self.assertRaisesRegex(ValueError, "boundaries"):
            plan(case, site, actors, authority, shoulder)
        site["roadway_shoulder_distinct"] = True
        case["sign_permitted_class"] = "tow_car"
        shoulder["permitted_class"] = "tow_car"
        with self.assertRaisesRegex(ValueError, "lawfully placed"):
            plan(case, site, actors, authority, shoulder)

    def test_position_and_intersection_variants_are_source_bound(self):
        case, site, actors, authority, shoulder = inputs()
        case.update(edge_type="right_edge", intersection_request="inside_intersection",
                    parallel_request="skewed", closeness_request="intentionally_offset")
        site.update(selected_edge_type="right_edge", curb_readback=False,
                    position_region="inside_intersection")
        shoulder.update(parallel_request="skewed", closeness_request="intentionally_offset",
                        body_yaw_target_deg=20.0, edge_distance_target_m=2.0)
        spec = plan(case, site, actors, authority, shoulder)
        self.assertEqual(spec["position"]["intersection"], "inside_intersection")
        self.assertEqual(spec["position"]["edge_distance_target_m"], 2.0)
        self.assertEqual(spec["position"]["body_yaw_target_deg"], 20.0)


if __name__ == "__main__":
    unittest.main()
