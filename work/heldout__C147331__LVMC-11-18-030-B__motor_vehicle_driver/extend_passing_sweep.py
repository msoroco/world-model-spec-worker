"""Build three exact Native crossing-fraction sweep constructions."""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE_SUFFIX = "passing_boundary_crossing"
PREFIX = "heldout__C147331__LVMC-11-18-030-B__motor_vehicle_driver__"
POINTS = {"passing_excursion-0000": .4,
          "passing_excursion-0001": .8,
          "passing_excursion-0002": .6}


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def build_construction(source_name, target_name, suffix, fraction):
    source = read(HERE / source_name)
    source["case_id"] = PREFIX + suffix
    for row in source["files"]:
        if row["path"] == "config.json":
            config = json.loads(row["content"])
            config["selected_case_id"] = PREFIX + suffix
            config["case"]["case_id"] = PREFIX + suffix
            config.setdefault("engineering", {})["crossing_fraction"] = fraction
            row["content"] = json.dumps(config, indent=2) + "\n"
        elif row["path"] in {"runner.py", "lane_construction.py", "lane_finalizer.py"}:
            row["content"] = (HERE / row["path"]).read_text()
    write(HERE / target_name, source)
    return digest(HERE / target_name)


def main():
    manifest_path = HERE / "delivery-construction-manifest.json"
    manifest = read(manifest_path)
    base = next(row for row in manifest["cases"] if row["case_id"] == PREFIX + BASE_SUFFIX)
    manifest["cases"] = [row for row in manifest["cases"]
                         if not row["case_id"].startswith(PREFIX + "passing_excursion-")]
    contract = read(HERE / ("measurement-contract-" + BASE_SUFFIX + ".json"))
    for suffix, fraction in POINTS.items():
        entry = deepcopy(base)
        entry["case_id"] = PREFIX + suffix
        entry["construction"] = "construction-delivery-" + suffix + ".json"
        entry["construction_sha256"] = build_construction(
            base["construction"], entry["construction"], suffix, fraction)
        entry.pop("offline", None)
        entry.pop("compatibility", None)
        entry.pop("physical_preparation", None)
        entry.pop("delivery_acceptance", None)
        for candidate in entry["candidates"]:
            source = candidate["construction"]
            candidate["construction"] = "construction-delivery-" + suffix + "-" + candidate["id"] + ".json"
            candidate["construction_sha256"] = build_construction(
                source, candidate["construction"], suffix, fraction)
            candidate.pop("offline", None)
            candidate.pop("compatibility", None)
        entry["measurement_contract"] = "measurement-contract-" + suffix + ".json"
        measurement = deepcopy(contract)
        measurement["case_id"] = PREFIX + suffix
        write(HERE / entry["measurement_contract"], measurement)
        manifest["cases"].append(entry)
    write(manifest_path, manifest)
    plan_path = HERE / "case-plan.json"
    plan = read(plan_path)
    passing = next(row for row in plan["cases"] if row["case_id"] == PREFIX + BASE_SUFFIX)
    plan["cases"] = [row for row in plan["cases"]
                     if not row["case_id"].startswith(PREFIX + "passing_excursion-")]
    for suffix, fraction in POINTS.items():
        row = deepcopy(passing)
        row["case_id"] = PREFIX + suffix
        row["purpose"] = ("Controlled passing path request at adjacent-lane fraction "
                          + str(fraction) + "; saved source decides actual clearance and crossing.")
        row["delivery_proofs"] = {"manifest": "delivery-construction-manifest.json"}
        plan["cases"].append(row)
    for disposition in plan["requirement_dispositions"]:
        ids = disposition.get("case_ids")
        if isinstance(ids, list) and PREFIX + BASE_SUFFIX in ids:
            for suffix in POINTS:
                if PREFIX + suffix not in ids:
                    ids.append(PREFIX + suffix)
    write(plan_path, plan)
    print("Built", len(POINTS), "exact passing sweep cases")


if __name__ == "__main__":
    main()
