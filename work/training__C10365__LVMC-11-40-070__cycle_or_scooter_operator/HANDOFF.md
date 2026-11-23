# LVMC-11-40-070 at C10365

## 2026-11-23 current runtime continuation

The frozen assignment now uses `law.text`; its SHA-256 is `902c6d14cde74e91231c542cf932e4f9081d381ba4e64da060f5a778c80dc882`. The eight unselected source-pinned candidates were rebuilt against that exact input. Each requests 600 frames at 20 Hz (30 seconds), four FFV1 cameras (1920x1080 overview and three 1280x720 detail views), and a 3840x1800 composed `raw.mkv`. The generated road extends to 180 m so the 30-second requested crossing stays on the authored lane. Native capture still has not run; role names and requested hand pose do not prove Police Officer authority or a visible instruction.

Pinned `runtime.py preflight` passed. Rebuilt copied-source proof has 8 positives and 32 negatives (`native/officer/request-proof.json`, SHA-256 `a63095f9ababebc0b0c4b051f87f564ac302385ca310ded33ca061e528e6916f`). Synthetic saved joins have 8 positives and 96 negatives (`native/officer/saved-proof.json`, SHA-256 `3702ea137c8365d8207f34cde0d1b3b6b813d73ed09396d9a84e1d5c8ff442dc`). Independent construction and trigger audit passed (`native/officer/independent-audit.json`, SHA-256 `6995e9dbf3fd6c6ae271104f84cebaecad9cb6ba347b3b4a7c458eae3573fd05`). All eight final constructions passed the pinned offline runtime, 24 tests (`native/officer/pinned-runtime-proof.json`, SHA-256 `18575b32ce5a3ef16c0e4cec4b2623364a821da48fd4ddca8996c2ab41fb2afb`); materialized-file audit passed (`native/officer/pinned-runtime-audit.json`, SHA-256 `81d740136b43d8d4957f4f4cb7b082b6cdc78dce0fe2b3bc699a78caa82b57e5`). A short synthetic four-camera FFV1 composition decoded as 3840x1800 (`native/officer/media-profile-proof.json`, SHA-256 `a32cd806bc1996d131dc8ed38d8f3c370d499f425d83e444bfb9367f5536939d`); this checks the media software path only.

Current `saved.py` rejects missing source cameras, mismatched dimensions/frame counts, stale raw media hashes and changed Native joins in original mode. It does not establish source pixels or statutory facts. The exact selected cases, saved-only selected processing proof and original visual/authority review remain CPU/source work. Keep this assignment partial; do not treat the older 480-frame paragraphs below as current proof.

## Historical handoff

Actor: `cycle_or_scooter_operator`. Frozen cell: `alley` / `travel` / `police_officer`.

Witness branch: Police Officer directs otherwise.

Comparison variable: `officer_direction_and_device_response`. Proposed physical probes: follow an applicable device with no contrary direction; follow a contrary officer direction. These are proposed controller and scene targets, not observed behavior or legal verdicts.

Source: `inputs/training__C10365__LVMC-11-40-070__cycle_or_scooter_operator/assignment.json`, SHA-256 `58c5a14d7c38851c0672c4e8cb5cf02eede790eec53a8fd6d5ffd541893c8419`. Summary status: `recovered_requires_source_review`; exact law text and witness take precedence.

Accepted membership IDs: none. No source-hashed equivalence receipt or accepted recording contents are available locally, so no reuse is claimed.

The unselected Native package in `native/officer/` now has eight source-pinned requests: primary, slower approach, elevated camera, and a moved officer staging position for both ordinary-device and contrary-officer probes. The same authored OpenDRIVE type-206 device, bicycle blueprint, lane, rate, weather and candidate camera policy are fixed within each pair. The case plan's second target is an officer-exception attempt, not a presumed violation.

`capture.py` attempts a bicycle, walker and distinct right-hand bone pose in generated CARLA, demands lane and landmark readback, saves 480 body/frame joins and three FFV1 cameras, and restores the world. The generic walker and its requested pose do not establish Police Officer identity, instruction meaning or official sign placement. This original capture has not run.

Exact copied-source CPU checks pass 8 positives and 32 material negatives. Synthetic saved-frame processing passes 8 positives and 96 negatives; it checks exact actor/request joins, contiguous Native/video frame and time joins, rider and officer eight-vertex bodies, velocity-consistent speed, rider displacement, stop/crossing geometry, device reference and reviewed officer direction timing. Original mode additionally requires three 480-frame FFV1 streams and a visual review hashed to the raw actors, frame map, generated map, capture receipt and each video. These are software checks only. An independent audit verifies eight candidates, four controlled pairs and three source-measured fallback trigger probes. Fallback 3 now moves the staged officer farther from the rider lane, and its synthetic measurement improves minimum separation. Eight rebuilt pinned `runtime.py offline` candidates pass 24 CPU tests; independent pinned audit verifies 96 materialized files and rejects a changed construction digest. The physical and legal outcome remains null. Original Native/media review is still required.

The exact-source review in `statutory-review.json` separates the three covered operator types, the three classes of official devices, vehicle applicability on this approach, the ordinary device-obedience branch and the Police Officer exception. A lawful controlled pair must prove that the officer's actual direction conflicts with the same applicable device instruction. Actor presence or a requested controller setting is insufficient evidence of an officer's direction. No case has been selected and Native representability of a controllable cycle/scooter operator and an explicit officer direction is still an open capability question. Original Native behavior, pixels and accepted recordings are later GPU checks; CPU software fixtures and pinned proofs remain required before readiness.

Resume by running the original CARLA attempt and reviewing officer authority, visible gesture meaning, device official status and timing from source media. Complete statutory coverage, accepted controlled comparisons and readiness only when the evidence passes.
