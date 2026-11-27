"""Append source-gated Native sweep bundles and synthetic CPU fixture recipes."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from build_diagnostics import synthetic_rows, synthetic_site
from freight_zone_sweep import CASES

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AID = HERE.name
LAW = "NRS-484B-507-1"
DONOR = ROOT / "work/testing__C135087__NRS-484B-517__motor_vehicle_driver/diagnostics"
SOURCE = DONOR / "loading_open_waiting"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value, compact=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False,
        separators=(",", ":") if compact else None,
        indent=None if compact else 2) + "\n")
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("returned sweep file exceeds 2 MiB: " + str(path))


def site_and_rows(case, exact, source_sha):
    site = synthetic_site(case, exact, source_sha)
    zone, road, clock = site["zone"], site["road"], site["clock"]
    if case.zone_boundary_offset_m is not None:
        zone.update(boundary_anchor_xy=[2, 0], boundary_inward_normal_xy=[1, 0],
                    boundary_anchor_source_sha256=source_sha,
                    parking_pose=[2 + case.zone_boundary_offset_m, 0])
    if case.civil_clock_offset_min is not None:
        from datetime import datetime, timedelta
        boundary = datetime.fromisoformat("2026-11-26T12:00:00-08:00")
        clock.update(effective_boundary_civil_time_iso=boundary.isoformat(),
                     effective_boundary_source_sha256=source_sha,
                     civil_time_iso=(boundary + timedelta(minutes=case.civil_clock_offset_min)).isoformat())
    if case.passenger_dwell_s is not None:
        site["passenger_dwell_controller_source_sha256"] = source_sha
    if case.freight_entry_headway_s is not None:
        road["freight_headway_controller_source_sha256"] = source_sha
    rows = synthetic_rows(case, exact, source_sha)
    for row in rows:
        frame = row["original_frame"]
        if case.zone_boundary_offset_m is not None and 280 <= frame < 600:
            row["ego_center_xy"] = zone["parking_pose"]
        if case.passenger_dwell_s is not None:
            completed = 300 + round(case.passenger_dwell_s * 20)
            if frame == 340:
                row["passenger_event"] = None
                row.pop("passenger_event_source_sha256", None)
            if frame == completed:
                row.update(passenger_event="boarding_completed", passenger_event_source_sha256=source_sha)
        if case.freight_entry_headway_s is not None:
            arrival = 280 + round(case.freight_entry_headway_s * 20)
            if frame == 290:
                row["freight_event"] = None
                row.pop("freight_event_source_sha256", None)
            if frame == arrival:
                row.update(freight_event="about_to_enter", freight_event_source_sha256=source_sha)
            row["freight_entry_blocked"] = arrival <= frame < arrival + 80
            if row["freight_entry_blocked"]:
                row["freight_entry_blocked_source_sha256"] = source_sha
            else:
                row.pop("freight_entry_blocked_source_sha256", None)
    return site, rows


def main():
    proposal = json.loads((HERE / "proposals/cases.json").read_text())
    sweep_cases = [c for c in proposal["cases"] if c["target_type"] == "judgment_sweep"]
    by_name = {c.name: c for c in CASES}
    selected_path = HERE / "execution-manifest.json"
    selected = json.loads(selected_path.read_text())
    diagnostic_path = HERE / "execution-manifest.compatibility-diagnostic.json"
    diagnostic = json.loads(diagnostic_path.read_text())
    plan_path = HERE / "case-plan.json"
    plan = json.loads(plan_path.read_text())
    selected["cases"] = [e for e in selected["cases"] if "__sweep_" not in e["case_id"]]
    diagnostic["cases"] = [e for e in diagnostic["cases"] if "__sweep_" not in e["case_id"]]
    plan["cases"] = [c for c in plan["cases"] if "__sweep_" not in c["case_id"]]
    config_path = HERE / "config.json"
    root_config = json.loads(config_path.read_text())
    root_config["supported_case_ids"] = [c["case_id"] for c in proposal["cases"] if c["target_type"] != "baseline"]
    write(config_path, root_config)
    root_construction_path = HERE / "construction.json"
    root_construction = json.loads(root_construction_path.read_text())
    next(item for item in root_construction["files"] if item["path"] == "config.json")["content"] = config_path.read_text()
    write(root_construction_path, root_construction)
    original_note = json.loads((HERE / "diagnostic-source-note.json").read_text())
    generator_donor = json.loads((DONOR / "loading_open_waiting-generator.json").read_text())
    donor_construction = json.loads((HERE / "construction-compatibility-pickup_load_prompt.json").read_text())
    for proposal_case in sweep_cases:
        exact = proposal_case["case_id"]
        name = exact.removeprefix(AID + "__")
        case = by_name[name]
        folder = HERE / "diagnostics" / name
        source_note = folder / "diagnostic-source-note.json"
        note = dict(original_note, case_ids=[exact])
        write(source_note, note)
        source_sha = sha(source_note)
        site, rows = site_and_rows(case, exact, source_sha)
        rows_path = folder / "freight-rows.json"
        write(rows_path, rows, compact=True)
        copied = []
        for relative in ("trace.jsonl", "video_frames.jsonl", "capture/native/frames.jsonl", "capture/evidence.jsonl"):
            target = folder / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((SOURCE / relative).read_bytes())
            copied.append({"path": relative, "source": str(target.relative_to(ROOT)), "sha256": sha(target)})
        provenance = folder / "acquisition-provenance.json"
        write(provenance, {"provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
                           "scope": "freight sweep source-shaped CPU compatibility only"})
        for target in (rows_path, source_note, provenance):
            copied.append({"path": target.name, "source": str(target.relative_to(ROOT)), "sha256": sha(target)})
        generator = copy.deepcopy(generator_donor)
        generator["files"]["capture/manifest.json"] = json.dumps({
            "acquisition": "synthetic_fixture", "case_id": exact,
            "extraction_confirmed": True, "frames": 900,
            "observation_contract_version": 2, "required_observations": [],
            "complete_driving_lanes": True,
            "native_map_facts": {"path": "native_map_facts.json",
                "sha256": hashlib.sha256(generator["files"]["capture/native_map_facts.json"].encode()).hexdigest()},
            "sources": {"road.xodr": hashlib.sha256(generator["files"]["road.xodr"].encode()).hexdigest(),
                        "trace.jsonl": sha(folder / "trace.jsonl")}}, indent=2) + "\n"
        generator_path = HERE / "diagnostics" / (name + "-generator.json")
        write(generator_path, generator, compact=True)
        recipe_path = HERE / "diagnostics" / (name + "-recipe.json")
        write(recipe_path, {"format": "worker-fixture-recipe", "sources": copied,
             "generator": {"source": str(generator_path.relative_to(ROOT)), "sha256": sha(generator_path)}})
        contract_path = HERE / "diagnostics" / (name + "-measurement-contract.json")
        write(contract_path, {"format": "worker-measurement-contract", "case_id": exact,
             "requirements": [{"disposition_index": 0, "requirement": "NRS-484B-507-1",
                "source": "inputs/planning/focused-coverage-20261016-v1/coverage-witnesses.json",
                "output_key": "freight_curb_zone", "method": "measure_freight_zone",
                "value_type": "object", "kind": "measured",
                "inputs": ["freight-rows.json", "diagnostic-source-note.json"]}],
             "negative": {"remove": ["freight-rows.json"],
                          "error_contains": "Missing required source: freight-rows.json"}})
        construction = copy.deepcopy(donor_construction)
        construction["case_id"] = exact
        construction["recording_description"] = proposal_case["recording_description"]
        files = {item["path"]: item["content"] for item in construction["files"]}
        config = json.loads(files["config.json"])
        config["selected_case_id"] = exact
        config["supported_case_ids"] = root_config["supported_case_ids"]
        config["case"].update(case_id=exact, name=name, conduct=case.conduct,
            material_action=case.material_action, activity_delay_s=case.activity_delay_s,
            hours=case.hours, passenger_action=case.passenger_action, freight_arrival=case.freight_arrival,
            zone_boundary_offset_m=case.zone_boundary_offset_m,
            civil_clock_offset_min=case.civil_clock_offset_min,
            passenger_dwell_s=case.passenger_dwell_s,
            freight_entry_headway_s=case.freight_entry_headway_s,
            recording_description=proposal_case["recording_description"])
        files.update({"config.json": json.dumps(config, indent=2) + "\n",
            "scene.json": json.dumps(site, indent=2) + "\n",
            "runner.py": (HERE / "runner_sweep.py").read_text(),
            "freight_zone.py": (HERE / "freight_zone_sweep.py").read_text(),
            "analysis.py": (HERE / "analysis_sweep.py").read_text()})
        files["tests/test_bundle.py"] = ("import unittest\nfrom runner import check\n\n"
            "class BundleTest(unittest.TestCase):\n"
            "    def test_exact_bundle(self):\n"
            "        case_id, case = check()\n"
            "        self.assertEqual(case_id, '" + exact + "')\n"
            "        self.assertEqual(case.name, '" + name + "')\n")
        construction["files"] = [{"path": p, "content": v} for p, v in files.items()]
        construction["measurement_plan"]["case_id"] = exact
        construction["diagnostic_only"] = True
        construction_path = HERE / ("construction-compatibility-" + name + ".json")
        write(construction_path, construction)
        diagnostic_entry = {"case_id": exact, "kind": "capability_research",
            "construction": construction_path.name, "construction_sha256": sha(construction_path),
            "fixture_recipe": str(recipe_path.relative_to(ROOT)),
            "measurement_contract": str(contract_path.relative_to(HERE)),
            "measurement_procedure": {"entrypoint": "analysis.py"}}
        diagnostic["cases"].append(diagnostic_entry)
        entry = copy.deepcopy(selected["cases"][0])
        for key in ("offline", "compatibility", "negative", "physical_preparation", "post_capture", "delivery_acceptance"):
            entry.pop(key, None)
        entry.update({k: diagnostic_entry[k] for k in ("case_id", "construction", "construction_sha256",
            "fixture_recipe", "measurement_contract", "measurement_procedure")})
        entry["source_gate"] = "Reviewed original marked freight zone, applicable hours and axis-specific physical source required at local dispatch."
        entry["acquisition"] = {channel["name"]: {"entrypoint": "analysis.py",
            "method": channel["method"], "evidence": "channel-" + channel["name"] + ".jsonl"}
            for channel in proposal_case["recording_description"]["channels"]}
        selected["cases"].append(entry)
        plan["cases"].append({"case_id": exact, "target_law_id": LAW,
            "purpose": "Source-gated engineering sweep " + name,
            "gap_ids": ["no-accepted-evidence"],
            "capture_disposition": "source_gated_original_capture_pending",
            "construction": "reviewed original C386226 freight site plus axis-specific source-gated controller",
            "measurement": "900 original Native frames and original-source saved audit",
            "physical_risk": {"status": "physical",
                "reason": "Curb alignment and activity visibility require local four-camera pixel review."}})
    write(diagnostic_path, diagnostic)
    write(selected_path, selected)
    write(plan_path, plan)
    print(json.dumps({"new_cases": len(sweep_cases), "selected_total": len(selected["cases"])}))


if __name__ == "__main__":
    main()
