"""Run the pinned sweep expander while retaining the source-gated gap.

The incomplete attention specification produces no new case. Future reviewed
sources must create and prove a complete specification before selection.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scenario_pipeline.batch_pipeline.sweeps import expand_sweeps


HERE = Path(__file__).resolve().parent


def _write(path: Path, data: dict) -> str:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expand() -> None:
    proposal_dir = HERE / "proposals"
    cases = json.loads((proposal_dir / "cases.json").read_text())
    template = json.loads((proposal_dir / "template.json").read_text())
    bindings = json.loads((proposal_dir / "bindings.json").read_text())
    original_ids = [row["case_id"] for row in cases["cases"]]
    if (len(cases.get("sweep_specs", [])) != 1
            or cases["sweep_specs"][0].get("sweep_id") != "alley_attention_observation"
            or cases["sweep_specs"][0].get("status") != "incomplete"):
        raise ValueError("exact source-gated attention sweep required")
    expand_sweeps(cases, templates=[template], bindings=bindings)
    if [row["case_id"] for row in cases["cases"]] != original_ids:
        raise ValueError("incomplete sweep cannot select new cases")
    index_path = proposal_dir / "semantic-index.json"
    index = json.loads(index_path.read_text())
    index["stages"]["cases"]["sha256"] = _write(proposal_dir / "cases.json", cases)
    _write(index_path, index)
    print("pinned sweep expander retained the incomplete attention spec and two source-gated selected cases")


if __name__ == "__main__":
    expand()
