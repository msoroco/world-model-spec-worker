# C101303 / NRS 484B.127(1) handoff

The frozen cell is a hill crest, lane change, and other vehicle. The statutory text requires a real following interval and due regard for both speeds, traffic, and highway condition. It gives no numeric lawful gap. The frozen local snapshot lists eight accepted recording IDs in demo-test and full-test; this clone contains neither their original videos nor their Native traces. Their status is retained as supplied context, not independently verified here.

## Resume

1. Run `python3.11 -m unittest discover -s tests -p test_following.py` in this directory.
2. Use `case-plan.json` for the two exact proposed test cases. Bind a CARLA map waypoint scan to `choose_crest`; inspect and record the selected connected lanes, crest, public highway context, and both vehicle models.
3. Construct synchronized 20 Hz Native actor-state, road-profile, environment, and four-camera capture. Connect the existing pinned capture/finalization/conversion stack; include positive and missing-source negative receipts per case, exact construction hashes, semantic proposals, and saved-only processing tests. Run the required offline and compatibility commands for each case and any physically justified fallback.
4. Compare the proposed pair with accepted demo-train cases for the law using original motion and pixels before dispatch. Make any scene change needed to establish a visible physical difference without changing the pair's controlled gap comparison. Run `python3.11 worker_check.py --complete --require-delivery-ready` only after all assignments and the shared branch review are implemented.

## Current limits

`following.py` and its CPU tests are construction and measurement helpers. They do not capture CARLA, finalize saved evidence, or establish legal acceptance. `inputs/coverage/branch-sources.json` and `inputs/coverage/candidate-cells.json` are absent, so the frozen full-branch source join is unavailable. Python 3.11 passes baseline checks, but the pinned CPU packages in `runtime/requirements-cpu.txt` are not installed and the interpreter has no pip module. No GPU or Native source has been used.
