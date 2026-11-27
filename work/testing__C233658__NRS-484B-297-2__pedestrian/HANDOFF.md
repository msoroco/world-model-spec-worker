# testing__C233658__NRS-484B-297-2__pedestrian

Status: **partial**. Four exact source-gated construction bundles pass the runtime offline check. The strict delivery-ready gate fails because the package is partial; no physical or canonical acceptance is claimed.

## Source and scope

NRS 484B.297(2) directs a pedestrian walking along a highway without a sidewalk to walk on the left side facing approaching traffic, except as subsection 6 provides. The supplied subsection 6 text in `inputs/coverage/branch-sources.json` concerns a traveler detouring from an obstructed sidewalk. C233658 fixes `road_without_sidewalk`, straight walking, another vehicle, and a pedestrian. A subsection 6 detour cannot be presumed from this cell. No accepted recording exists in this assignment's frozen `evidence.json`. No exact law/actor judgment range exists in the supplied range file. No legal numeric side or facing threshold is invented.

The original site packet must substantiate public highway status, public vehicular access, the highway boundaries, absence of a qualifying sidewalk throughout the walking segment, and subsection 6 nonapplicability. `site_source.py` checks source hashes and review fields before any live action. Its fixture test proves rejection of missing and stale sources, not the actual site facts.

## Exact coverage plan

| Exact case suffix | Approach | Pedestrian side and heading |
| --- | --- | --- |
| `east_approach_left_side` | eastbound vehicle | left highway side, facing the vehicle |
| `east_approach_right_side` | eastbound vehicle | right highway side, facing the vehicle |
| `west_approach_left_side` | westbound vehicle | left highway side, facing the vehicle |
| `west_approach_right_side` | westbound vehicle | right highway side, facing the vehicle |

All full IDs are the assignment ID followed by `__` and the suffix. The plan has `east_approach_side`, `west_approach_side`, and `approach_direction` comparisons. The first two vary lateral walking side while retaining approach direction, heading, camera plan and duration. The third verifies mirrored approach directions while retaining the left-side/facing relation. Physical readback must verify intended routes and sides; the authored coordinates are only construction requests.

`case-plan.json` lists the one selected requirement disposition, original observations, gap ID, witness review and camera plan. `road_geometry.py` supplies mirrored routes. `build_bundles.py` creates each inline construction, config, measurement contract and case spec under `cases/`. `runner.py --check` validates the exact bundle without CARLA. `walking_measure.py` measures source-shaped original pedestrian side, facing, approach and progress; `analysis.py` contains a saved finalizer with source-hash and frame/time joins, but its positive and negative runtime compatibility remain untested. The runner's live path currently stops after source validation; actual Native capture remains unimplemented. There are no fallbacks yet; walker/controller and camera risks need measurable candidate tuning, proof and independent review before ready status.

## Proven checks

Run with `PYTHONDONTWRITEBYTECODE=1` and `SCENARIO_PIPELINE_OUTPUT_ROOT` set under `.runtime-work/` before any direct runtime import:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C233658__NRS-484B-297-2__pedestrian/tests -v
PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/testing__C233658__NRS-484B-297-2__pedestrian/build_bundles.py
PYTHONDONTWRITEBYTECODE=1 SCENARIO_PIPELINE_OUTPUT_ROOT="$PWD/.runtime-work/pedestrian-output" .venv-cpu/bin/python runtime.py offline --manifest work/testing__C233658__NRS-484B-297-2__pedestrian/execution-manifest.draft.json --case testing__C233658__NRS-484B-297-2__pedestrian__east_approach_left_side --output .runtime-work/pedestrian-offline-new
PYTHONDONTWRITEBYTECODE=1 SCENARIO_PIPELINE_OUTPUT_ROOT="$PWD/.runtime-work/pedestrian-output" .venv-cpu/bin/python worker_check.py --assignment testing__C233658__NRS-484B-297-2__pedestrian --complete --require-delivery-ready
```

The first test passed four tests, and runtime offline passed all four exact cases. Their small logs and SHA256 values are in `result.json`. `strict.log` retains the current readiness failure. The generator does not establish CARLA motion.

## Remaining CPU work

1. Implement source-gated CARLA pedestrian and vehicle spawning, 20 Hz original transform capture, synchronized four-camera capture, FrameMap, ownership cleanup/world restoration, and actual completion checks. Remove the explicit unfinished Native error in `runner.py` only when this code is tested.
2. Complete and test the saved finalizer and measurement contracts against case-specific diagnostic recipes; obtain positive and missing-source negative runtime compatibility proofs for every case and each justified fallback.
3. Author canonical semantic stage proposals and semantic index. Add saved-only processing proofs, independent delivery and comparison audits with negative rejection, physical/lifecycle fixture tests, complete execution manifest and a concrete queue proposal.
4. Independently review the exact law and branch alternatives, then rerun the strict assignment gate. Actual physical outcome remains for the local GPU operator after CPU readiness.
