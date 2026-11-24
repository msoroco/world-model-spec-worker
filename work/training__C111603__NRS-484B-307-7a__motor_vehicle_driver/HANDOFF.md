# NRS-484B-307-7a at C111603

Status: partial; source-bound arrow and other-vehicle timing requests pass pinned CPU offline checks.

Actor: `motor_vehicle_driver`. Frozen cell: `intersection` / `turn` / `other_vehicle`.

Exact source: NRS 484B.307(7)(a). The full text and source hash are retained in `case-plan.json`; extracted summary status is `recovered_requires_source_review`. Witness branch: Other-traffic yield duty.

Controlled variable: `yield timing under flashing yellow turn arrow`. Requested pair: turn on flashing yellow arrow after yielding to lawful users; turn on flashing yellow arrow ahead of lawful user. These are construction requests, not measurements or legal verdicts. The baseline is unselected.

Statutory branch dispositions: 1. Review each exception and dependency against the exact text before physical selection. Accepted membership rows: 0; no source-hashed equivalence receipt is available, so reuse is unclaimed.

Open work: Two source-bound 30-second turn requests and their offline proofs now exist. Original Native acquisition, saved processing, compatibility and physical/legal review remain unverified.

Resume: build Native geometry, actor control, cameras and mandatory capture for each runnable branch; prepare four distinct source-preserving constructions per selected case; run exact pinned-runtime offline and compatibility checks, saved positive/negative fixtures and an independent audit. Set `ready` only after those CPU proofs pass.

Source-context review: Arrow may be displayed alone or with other indications; only its indicated movement or one permitted by a concurrent indication is allowed. Pedestrian and other-traffic yield duties are separate branches.

## Flashing-yellow arrow and other-traffic construction checkpoint, 2026-11-23

`native/request.py` binds the frozen NRS 484B.307(7)(a) text, authors an intersection with one requested flashing-yellow right arrow, and generates two 600-frame/20 Hz motor-vehicle right-turn requests. The arrow program and other-vehicle route are identical; only ego release changes. The requested first entry is frame 325 after the other vehicle has cleared the intersection, versus frame 205 while that vehicle is within it. Five changed-source cases reject: truncated frame inventory, altered arrow, changed other route, fabricated lawfulness and fabricated Native observation. Both exact draft constructions pass pinned `runtime.py offline`; see `yellow-arrow-cpu-proof.json` for hashes.

This proof concerns requested motion only. Arrow authorization/facing and actual flash pixels, original vehicle motion, other-traffic lawfulness, pedestrian presence and cautiousness are unverified. No legal right-of-way conclusion follows from temporal occupancy. Remaining CPU work: implement four-camera Native acquisition, saved-only measurement/finalization and positive/negative compatibility, physical-risk fallbacks, independent audits, the separate pedestrian and concurrent-indication branches, and strict selected delivery.
