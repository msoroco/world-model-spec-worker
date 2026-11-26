# testing__C380107__NRS-484B-208-1__motor_vehicle_driver

Status: partial exact-case measurement checkpoint, 2026-11-23. No delivered original capture or legal conclusion is claimed.

NRS 484B.208(1), with subsection 2, addresses continued operation below the posted limit in the extreme left lane of a controlled-access multilane highway while a faster motor vehicle overtakes from the rear, subject to several exceptions. This assigned cell specifically requires an active qualified HOV-lane exception comparison. Frozen accepted evidence for this exact assignment is zero recordings; no exact-law judgment ranges were identified. The conditional witness remains a proposal, not accepted physical evidence.

## Constructed CPU work

`case-plan.json` specifies nine unexecuted exact variants and eight controlled comparisons: core encounter, actually qualified HOV operation, ineligible and inactive HOV designation, posted-limit equality, rear vehicle not faster, moving right, city/town boundary, and hazard necessity. The plan requires independent posted-limit, controlled-access, extreme-left lane, driver, knowledge, geography, HOV hours/signs/access/occupancy/category/compliance and other-exception sources. HOV designation alone does not establish eligibility.

`hov_encounter_observations.py` consumes a hash-sealed original Native context, source receipt, and 20 Hz ego/rear actor trace. It validates exact identity, original provenance, two distinct marked same-direction lanes, lane identity, posted limit, cadence, speeds and signed rear gap. It reports below-limit samples, faster rear vehicles in the same extreme-left lane, and the first signed-gap crossing frame. It leaves legal knowledge, continued operation and HOV qualification judgments unresolved and physical acceptance unverified. Seven focused tests include positive extraction and rejection of diagnostic, changed, source-incomplete and lane-incomplete inputs.

## Proofs

- `.venv-cpu/bin/python runtime.py preflight`: exit 0; `cpu-preflight.log` SHA256 `b9fea8700c72d1d20657fd867beb294669e74b80cc73461e1121090c23a94a63`.
- `.venv-cpu/bin/python -m unittest discover -s work/testing__C380107__NRS-484B-208-1__motor_vehicle_driver/tests -v`: exit 0; `cpu-hov-tests.log` SHA256 `f2803ef56b51c9cba9132e6d364a5c923e9a5dc4343a492218d5775b0ae58e6b`.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C380107__NRS-484B-208-1__motor_vehicle_driver --complete`: exit 0; `assignment-check.log` SHA256 `7c149712cdc13f38f0832182f2902822ef520123b8e721d926228b3b5be45dd5`.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C380107__NRS-484B-208-1__motor_vehicle_driver --complete --require-delivery-ready`: exit 1 as truthful partial; `strict-gate.log` SHA256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`. It fails the all-ready requirement.

## Remaining CPU and physical work

Build and prove exact Native scene/controller, full original 20 Hz four-camera capture, source-bound finalizer and semantic proposal, saved compatibility/processing, and delivery/comparison audits for all variants. Resolve applicable HOV requirements including NRS 484B.323(1) before any legal exception determination. Actual CARLA motion, lane markings, HOV signs and camera visibility remain physical checks after CPU preparation. No dependency or missing-tool blocker is asserted.

## 2026-11-26 construction checkpoint

Canonical semantic draft validates with 18 selected exact cases and 11 comparisons. SHA-gated original highway, HOV authority, actor and camera Native construction has been written; diagnostic fixtures are explicitly synthetic. Eleven focused CPU tests and 18/18 pinned offline construction proofs passed. Saved compatibility, delivery and comparison proofs remain in progress; result status is partial.
