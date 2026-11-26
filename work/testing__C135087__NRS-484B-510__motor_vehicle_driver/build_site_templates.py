"""Create exact-case blank review forms; these are not source packets."""

import json
from pathlib import Path

from reviewed_site import ROLES
from site_geometry import VIEWS


ROOT = Path(__file__).resolve().parent


def main():
    plan = json.loads((ROOT / "case-plan.json").read_text())
    folder = ROOT / "site-templates"
    folder.mkdir(exist_ok=True)
    for case in plan["cases"]:
        case_id = case["case_id"]
        suffix = case_id.removeprefix(ROOT.name + "__")
        params = case["scenario_parameters"]
        template = {
            "form_status": "unfilled_not_a_reviewed_source_packet",
            "case_id": case_id, "cell_id": "C135087", "map_id": None,
            "restricted_purpose": params["restricted_purpose"],
            "zone_start_m": params["zone_start_m"],
            "zone_end_m": params["zone_end_m"],
            "reviewer": None, "reviewed_at": None,
            "sources": {role: {"path": None, "sha256": None} for role in ROLES},
            "native_binding": {
                "geometry_source": {"path": None, "sha256": None},
                "map_name": None,
                "approach_route": [
                    {"station_m": min(-5, params["entrant_start_m"]), "location_m": None},
                    {"station_m": params["zone_end_m"] + 5, "location_m": None}],
                "blueprints": {role: None for role in ("subject", "entrant", "passenger")},
                "fixed_actors": {role: {"actor_id": None, "type_id": None}
                                 for role in ("zone_sign", "zone_curb")},
                "camera_poses": {view: {"location_m": None, "rotation_deg": None}
                                 for view in VIEWS},
                "passenger_spawn_m": None, "passenger_door_m": None,
                "entrant_access_polygon_m": None,
                "observation_tolerances_m": {name: None for name in ("station", "door", "access")}}}
        (folder / (suffix + ".json")).write_text(json.dumps(template, indent=2,
                                                               sort_keys=True) + "\n")
    print("wrote", len(plan["cases"]), "unfilled exact-case review forms")


if __name__ == "__main__":
    main()
