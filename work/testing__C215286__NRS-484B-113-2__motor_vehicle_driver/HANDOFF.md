# testing__C215286__NRS-484B-113-2__motor_vehicle_driver

Status: partial CPU construction and audit; no delivery-ready claim.

Exact assigned branch: NRS 484B.113(2), backing on or over a crosswalk, C215286 motor vehicle driver. The statute also names intersection and street corner, but this assignment fixes the crosswalk branch. There is no statutory numeric threshold or judgment range for this assignment. A physical body-boundary contact probe is an engineering geometry probe, not a legal cutoff.

## Coverage and accepted evidence

`case-plan.json` names exact `reverse_clear`, `reverse_tangent`, and `reverse_overlap` cases. It links clear/contact and clear/overlap comparisons with fixed map, marking, vehicle, driver, capture rate and reverse condition. The one frozen accepted marked-crosswalk recording is preserved and reviewed in `evidence_review`; its exported metadata reports acceptance and 700 frames, while original trace and video are absent. Its body-crosswalk relation and comparison isolation cannot be inferred from metadata, so it is not counted as full branch coverage.

## Implemented CPU construction and proof

`crosswalk_delivery.py` validates an original map hash, crosswalk polygon/source, vehicle blueprint, driver/district sources, spawn transform source and nondegenerate reverse route. It lazily spawns the ego through an injected Native world and checks map and blueprint readback. It issues reverse/hold control, measures 20 Hz original-frame body polygon versus crosswalk polygon with velocity and reverse gear, and audits an expected physical relation only while backing. Its comparison audit requires two distinct original sources, a common map/crosswalk source and frame window, and an observed relation change. It returns no legal verdict.

`.venv-cpu/bin/python -m unittest discover -s work/testing__C215286__NRS-484B-113-2__motor_vehicle_driver/tests -v` passed 12 tests. `cpu-tests.log` SHA256: c1216526e41ef083fb3b6659c3166b0718b582596bc093d96734986f88d39c52. Exact static check `.venv-cpu/bin/python worker_check.py --assignment testing__C215286__NRS-484B-113-2__motor_vehicle_driver --complete` passed; log `assignment-check.log`.

## Next CPU actions

1. Export a source-hashed original C215286 marked-crosswalk polygon, district and reverse route packet; bind exact construction for all three cases and assess whether a tested fallback is needed for edge contact.
2. Author the exact execution manifest, canonical stage proposals, full original-frame finalizer, four-camera capture profile and source-specific diagnostic recipes.
3. Run exact offline and positive/negative compatibility proofs for each case and any candidate, then test `runtime.py process-saved` with independent full-video, source-decode, delivery and comparison audits.
4. Rerun the exact strict assignment gate. Actual CARLA motion and camera visibility remain later physical checks, separate from the unfinished CPU package.

## Exact offline construction bundles

`execution-manifest.json` binds all three exact inline constructions under `cases/`. Each bundle has `runner.py`, `scene.json` and two exact-case tests. `runtime.py offline` passed for `reverse_clear`, `reverse_tangent`, and `reverse_overlap` with receipts in `cpu-offline-*.log`; these check software identity and materialization only. The Native execution path in `runner.py` intentionally fails until original C215286 source packet and complete capture/finalization code are bound. No compatibility or delivery readiness is claimed.

- `cpu-offline-reverse_clear.log` SHA256: `11133046e26ff39bfd368df7bedaf429c166289dac27cb401e3ee42764aa601c`.
- `cpu-offline-reverse_tangent.log` SHA256: `f693ce34611c8f70445abf3b6b8c74cc04c8cb04506a532740d187144088097a`.
- `cpu-offline-reverse_overlap.log` SHA256: `3cf275f77dd70acae3575a05094fc87e4a6f0dd61a6edd83027d62e780ba03e2`.

## Saved-source finalizer increment

`analyze_source.py` reads a reviewed original map packet and `channels/reverse-body-crosswalk.jsonl`, checks the frame-file SHA256 and exact polygon equality, then emits physical measurement and unresolved legal judgment. The focused suite now has 12 passing tests including removal of the required frame source and changed bytes. This is a source-bound component test, not the full `runtime.py compatibility` gate; Native-shaped four-camera diagnostic, canonical proposal/measurement contract and complete process-saved outputs remain to author.
