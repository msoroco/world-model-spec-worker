# LVMC 11.38.030, C412982 motorcycle or moped operator

Status: **CPU delivery prepared**. The exact scoped strict gate passed after six source-gated Native bundles, six offline proofs, six positive and six negative compatibility proofs, six saved-only lifecycle proofs, six independent delivery audit positive/negative protocol pairs, and five independent comparison audit tests. No CARLA episode or physical acceptance is asserted. The frozen evidence inventory has zero accepted recordings, so six new recordings are planned and none are reused.

## Exact source and scope

The text in `inputs/testing__C412982__LVMC-11-38-030__motorcycle_or_moped_operator/assignment.json` says: “No motorcycle or motor scooter shall be ridden upon any sidewalk of the City.” The selected actor ID is broader than those two named device categories; this package requires original motorcycle or motor scooter classification and does not infer moped coverage. The one frozen witness (index 288) is conditional and requires City location, pedestrian-use sidewalk boundaries, mounted riding, route continuity, body footprint and device identity. Undefined terms and possible state/municipal definition composition remain for local legal review. No numerical legal threshold was created. The 40 m motion goal is an engineering completion probe only.

The exact cases in `case-plan.json` are:

- `motorcycle_riding_sidewalk_north`: mounted motorcycle riding on the north City sidewalk.
- `motorcycle_riding_sidewalk_south`: same named category on the other City sidewalk.
- `motor_scooter_riding_sidewalk`: the second named device class on the north City sidewalk.
- `motorcycle_riding_road`: adjacent-road surface contrast.
- `motorcycle_walking_sidewalk`: walking rather than mounted riding contrast.
- `motorcycle_riding_outside_city`: surveyed North Las Vegas sidewalk contrast. This case requires its own original municipal boundary packet; a cell label is not jurisdiction evidence.

Five paired comparisons test sidewalk side, device class, surface, mounted conduct and City jurisdiction. The City boundary pair permits the original map/site to differ, while preserving the common device, conduct, camera and measurement policy. The other comparisons require identical reviewed site-source hashes, camera plan and duration. `comparison_audit.py` rejects missing acceptance, changed fixed inputs and missing measured actor-body surface overlap history.

## Construction and sources

`sidewalk_030.py` defines the exact physical cases, finite sidewalk and road polygons, route placement, City/source gates and 20 Hz measurement join. It checks the reviewed packet and its six original source file hashes before CARLA import. `runner.py` remains CARLA-lazy and requires `C412982_LVMC030_REVIEWED_SITE_PACKET`. `native_sidewalk_030.py` spawns and reads back the source-qualified device and walking operator as applicable, controls a reviewed route, writes the original actor bounding-box body polygon in each frame alongside center positions and mounted-riding evidence, obtains four synchronized cameras, seals source hashes and verifies world restoration. `camera_capture.py` implements the four-view capture profile. Local acquisition must review asset existence and rideability, original City boundary survey, sidewalk purpose, route motion and pixels before acceptance.

`analysis.py` processes saved sources only, verifies original source hashes and frame identity, joins every frame to its source-qualified municipal packet and mounted-riding evidence, measures actor-body polygon overlap with the selected sidewalk or road target, emits measured device, conduct, surface and municipality channels, and leaves the legal verdict null. A target check cannot pass from a center point or case label alone. Polygon intersection includes containment, crossed edges and actual contact; a regression test rejects disjoint collinear edges. Each case has its own configuration, complete inline construction, diagnostic generator and measurement contract under `cases/` and `diagnostics/`. Fixture outputs stay under `.runtime-work/c412982-lvmc030-owner/`; none are returned as original footage. `proposals/` contains all five canonical semantic stages and the source-bound index.

Every manifest case has an explicit `candidate_risk` assessment. It has no fallback because no measured alternative spawn or route trigger exists before the first original Native run. If that run identifies a concrete asset or camera failure, prepare a source-preserving candidate and re-run its exact CPU proofs before local selection. The six `physical-*-receipt.json` files test complete, incomplete and missing evidence outcomes plus native-exit, owner-release and saved-processing order. `delivery_audit.py` checks original seal, full source hashes, actual frames, independent pixel review, saved processing and current media decode receipt; `delivery_probe.py` proves missing-source rejection. `queue-proposal.json` supplies concrete exact-case prepare, execute, owner release, saved postprocess, independent source audit and accept commands, plus five comparison audit commands. The lead owns shared queue integration.

## Reproduction and limitations

From repository root, with the pinned CPU environment and Lean validator already installed:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python -m unittest discover -s work/testing__C412982__LVMC-11-38-030__motorcycle_or_moped_operator/tests -v
PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/testing__C412982__LVMC-11-38-030__motorcycle_or_moped_operator/comparison_probe.py
SCENARIO_PIPELINE_OUTPUT_ROOT="$PWD/.runtime-work/c412982-lvmc030/output" PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python worker_check.py --assignment testing__C412982__LVMC-11-38-030__motorcycle_or_moped_operator --complete --require-delivery-ready
```

The last command passed after the original actor-body footprint/source join repair. The lead independently repeats the scoped gate and reconciles the already published shared queue. Proof scripts `prove_runtime.py`, `prove_lifecycle.py` and `prove_delivery.py` are provided for rebuilding only after affected sources change. CPU fixtures establish software behavior and rejection paths, never actual rider motion, City geography, camera visibility, statute compliance or canonical set acceptance. No files in frozen inputs, runtime or batch were changed.
