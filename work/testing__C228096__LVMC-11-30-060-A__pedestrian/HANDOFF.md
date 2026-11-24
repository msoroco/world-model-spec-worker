# testing__C228096__LVMC-11-30-060-A__pedestrian

Status: partial source inventory. No case or recording is proposed by this checkpoint.

Exact law: LVMC 11.30.060(A); with 11.30.060(C) — Every pedestrian crossing a roadway at any point other than within a marked crosswalk or within an unmarked crosswalk at an intersection shall yield the right-of-way to all vehicles upon the roadway. The foregoing rules in this Section shall have no application under the conditions stated in Section 11.30.070 when pedestrians are prohibited from crossing at certain designated places.
Assigned branch(es): Outside-crosswalk crossing beginning with road entry.
Cell: C228096 (road, enter_road, other_vehicle); actor: pedestrian.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Read the full exact law and applicable definitions, branch topic inventory, source witnesses and original scenario skills. Split all alternatives and exceptions; resolve the accepted-evidence sufficiency against available source summaries.
2. Author every required exact case and controlled comparison, including below/inside/above judgment probes when applicable. Map observations to actual capture sources.
3. Implement and CPU-test construction/controllers, finalizers, semantic proposals, saved-only processing, delivery/comparison audits and risk-based fallbacks where concrete risks justify them. Add physical-risk assessment for every manifest case.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C228096__LVMC-11-30-060-A__pedestrian --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

## 2026-11-23 CPU checkpoint

The outside-crosswalk duty requires a roadway crossing point outside both marked and unmarked intersection crosswalks, pedestrian yielding to all vehicles upon the roadway, and separate review of the 11.30.070 prohibited-place exception. `case-plan.json` now has four unselected constructions and three isolated comparisons for pedestrian yield, vehicle presence and designated prohibition. No accepted recordings exist in the frozen inventory.

`outside_crosswalk_entry.py` binds original source SHA256, requires roadway/crossing-point and marked/unmarked crosswalk readback, brackets first pedestrian road entry, and reports vehicle roadway IDs and yield observation separately. Five synthetic CPU tests cover yielding, non-yielding, unmarked-crosswalk rejection, prohibited-place retention and absent entry. A yield observation at entry does not prove yielding throughout crossing.

| File | SHA256 |
| --- | --- |
| `case-plan.json` | `0175274e26ab3e9e9fef1fd351f28a84e2ed4ec5c6fdbd745baa6fb6711cc861` |
| `outside_crosswalk_entry.py` | `83233f84aac1bba1f7fdf723641a11c92ea8a1f1407fc3b02741f47ce0630da2` |
| `tests/test_outside_crosswalk_entry.py` | `1d69bf7b860cf77529ca802fe399500f2ee58a504267f24d8561a28256723f13` |
| `preflight.log` | `04a8adabf3a86ccfeab5caefb24d933b1e886c79afd32d3b356280d843791ddc` |
| `unittest.log` | `f1ede14a8cd1bcd3f0534e52b1fc83091e02bd92c78b96c5ea8de68105673075` |
| `static.log` | `6e4c8f0302bb56a7b8c877d0b8e09db2fc9d772ce3af1efbe47552149ae54b4b` |
| `strict.log` | `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a` |

Preflight exit 0; five tests exit 0; scoped static exit 0; exact scoped strict exit 1 because package status remains partial. Command bindings are in `result.json`.

Next CPU work: construct/read back crossing point outside marked and unmarked intersection crosswalks, vehicle and pedestrian original trajectories; resolve 11.30.070 exception from source; implement saved finalizer, exact positive/negative compatibility and independent delivery/comparison audits. CARLA motion and camera quality follow CPU readiness.
