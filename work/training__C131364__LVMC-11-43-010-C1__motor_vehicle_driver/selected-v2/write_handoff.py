"""Put the current selected CPU checkpoint ahead of historical notes."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
handoff = ROOT / "HANDOFF.md"
marker = "## 2026-11-24 selected CPU delivery checkpoint"
old = handoff.read_text()
if marker in old:
    old = old[old.index("\n## ", old.index(marker) + len(marker)) + 1:]


def show(relative):
    value = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
    return f"`{relative}` SHA-256 `{value}`"


result = json.loads((ROOT / "result.json").read_text())
head = f"""{marker}

Status is `{result['status']}` with `{result['readiness_kind']}` after the exact
assignment-scoped strict CPU delivery gate passed. The exact selected left-turn pair is in
{show('selected-v2-manifest.json')}. Each case has a source-hashed 600-frame,
20-Hz, four-camera primary and symmetric controller fallback. All four exact
selected paths passed pinned `runtime.py offline`, 11-check public
`runtime.py compatibility` with missing-source rejection, and recorded-only
`runtime.py process-saved`. Durable receipts reside under `selected-v2/proofs/`.

The independent CPU source and comparison audit passes:
{show('selected-v2/audit.json')}. Canonical semantic stage validation passes:
{show('selected-v2/semantic-validation.json')}, with source-bound stage index
{show('proposals/semantic-index.json')}. The exact `full-train` delivery contract
validates both selected cases, including positive and negative audit tests:
{show('selected-v2/delivery-contract-validation.json')}.

Original-attempt delivery audit implementation is
{show('selected-v2/delivery_audit.py')}. Its CPU fixtures pass for both cases;
each negative rejects a changed driver-reference original camera hash.
Original-attempt comparison audit implementation is
{show('selected-v2/comparison_audit.py')}; CPU positive passes and altered-road
negative rejects, as proven by {show('selected-v2/comparison-positive.log')} and
{show('selected-v2/comparison-negative.log')}. Its actual mode requires both
original Native attempts and independent physical review receipts, checks
each sealed source and all 600 original frame/camera joins through the delivery
auditor, verifies common fixed conditions, and demands observed distinct
circulating lanes. No actual mode was run and no physical or legal finding is
claimed.

The canonical root package is now materialized at
{show('execution-manifest.json')} with root `construction.json`, `runner.py`,
`config.json`, and `tests/test_route.py`. Pinned execution-manifest validation
and primary package compatibility receipt checks pass for both exact cases:
{show('selected-v2/canonical-validation.json')}. Three synthetic physical
outcome fixtures per case cover complete, incomplete, and missing evidence;
their source-bound proof receipts are
{show('selected-v2/physical/witness1/proof.json')} and
{show('selected-v2/physical/witness2/proof.json')}. Root four-test suite passes:
{show('selected-v2/root-unittest.log')}. These remain CPU fixture outcomes,
not observed original passage outcomes.

Statutory branch review is {show('proposals/statutory-branch-review.json')}.
This assignment's frozen cell supports the left-turn pair. The exact-law
`training__C131055__LVMC-11-43-010-C1__motor_vehicle_driver` assignment must
bind the separate U-turn alternative; do not treat this left-turn pair as
covering it. Original legal interpretation remains for local review.

Replay commands from repository root (all scratch must stay under
`.runtime-work/`):

```sh
export PYTHONDONTWRITEBYTECODE=1
export SCENARIO_PIPELINE_OUTPUT_ROOT="$PWD/.runtime-work/c131364-selected-refresh"
.venv-cpu/bin/python work/{ROOT.name}/selected-v2/audit.py
.venv-cpu/bin/python work/{ROOT.name}/selected-v2/validate_semantic.py
.venv-cpu/bin/python work/{ROOT.name}/selected-v2/validate_delivery_contract.py
.venv-cpu/bin/python work/{ROOT.name}/selected-v2/validate_canonical.py
.venv-cpu/bin/python work/{ROOT.name}/selected-v2/comparison_audit.py --cpu-test positive
.venv-cpu/bin/python work/{ROOT.name}/selected-v2/comparison_audit.py --cpu-test negative
.venv-cpu/bin/python worker_check.py --assignment {ROOT.name} --complete
.venv-cpu/bin/python worker_check.py --assignment {ROOT.name} --complete --require-delivery-ready
```

The comparison negative must exit nonzero with `Comparison fixed condition
differs: road_sha256`. The case plan now binds the exact camera profile and
every frozen observation term to retained source or the separate U-turn handoff.
The full assignment-scoped strict CPU gate passed on current source hashes.
Local physical work requires two actual Native
captures, original pixel/roundabout/left-turn/lane-history review receipts,
and original comparison audit. Historical notes follow.

"""
handoff.write_text(head + old)
