# C376646 CPU handoff — NRS 484B.250(4)

Status: **partial**. Frozen accepted-evidence inventory is empty. Exact blind-intersection branch requires installed, uncovered and wholly inoperative vehicular signal heads; the marked-line, near-side-crosswalk and nearest-view stopping hierarchy; then cautious motion yielding to previously stopped or already present vehicles. No physical or legal outcome is inferred from synthetic diagnostics.

## Current construction

Four selected case IDs are in `case-plan.json`: `stop_line_other_inside`, `crosswalk_other_previously_stopped`, `nearest_view_other_inside`, and the additional prohibited-condition `stop_line_no_halt`, each prefixed by this assignment ID. `runner.py` is a lazy-CARLA Native capture with two sourced approaches, complete-body boundary feedback, all-head Off readback/restoration, and four original cameras. Source-bound `site-review.json`, `site-sources.json` and authored OpenDRIVE files are packaged per case in `cases/<suffix>/construction.json`; `review-draft-manifest.json` binds all four current constructions. Each exact `runtime.py offline` check passed; logs are `cases/<suffix>/primary-offline.log`. All four `runtime.py fixture` materializations passed, with logs in each case folder. Seven package CPU tests pass in `cpu-tests.log`, including the rolling-stop negative and a counterfactual priority-basis measurement. Current diagnostic positive cases show a halt; the no-halt case has no ego full-halt sample. The existing crosswalk diagnostic happens to show both other-priority predicates true, so its physical comparison is not yet isolated. The runner's crosswalk route waits for the other to clear, while the other-inside route waits for entry; this remains to be demonstrated with source-bound saved proof.

The authored site packets were adapted from prior C24757 worker source candidates. They are source-bound CPU planning material, not reviewed Native facts for C376646. They retain descriptive C24757 map names. Physical installed and uncovered signal appearance, true blind sight lines, stop-reference visibility, completed yielding and camera quality remain later Native checks. The source-hash and all-head inventory code reject unsourced site changes and uninventoried heads.

## Next CPU actions

Bind the four cases into the canonical semantic proposals and requirement dispositions, then create measurement contracts and per-case saved-only processing receipts. Run source-bound positive/negative compatibility, physical-outcome fixture tests, justified fallbacks and independent delivery/comparison audits. Build the final execution manifest and GPU queue rows. Run the exact scoped strict gate before marking ready. These are worker-owned tasks; no missing runtime dependency or GPU prevents the CPU work.

Resume:

```sh
.venv-cpu/bin/python -m unittest discover -s work/testing__C376646__NRS-484B-250-4__motor_vehicle_driver/tests -v
.venv-cpu/bin/python worker_check.py --assignment testing__C376646__NRS-484B-250-4__motor_vehicle_driver --complete
.venv-cpu/bin/python worker_check.py --assignment testing__C376646__NRS-484B-250-4__motor_vehicle_driver --complete --require-delivery-ready
```

No frozen input, runtime or batch file was edited; no Git command was run.
