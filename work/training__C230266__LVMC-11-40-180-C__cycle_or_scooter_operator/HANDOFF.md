# LVMC-11-40-180-C at C230266

Actor: `cycle_or_scooter_operator`. Frozen cell: `road` / `travel` / `pedestrian`.

Witness branch: Pedestrian-controlled sidewalk encounter.

Comparison variable: `sidewalk_pedestrian_pass`. Proposed physical probes: yield and give audible signal before passing; pass without audible signal. These are proposed controller and scene targets, not observed behavior or legal verdicts.

Source: `inputs/training__C230266__LVMC-11-40-180-C__cycle_or_scooter_operator/assignment.json`, SHA-256 `1b9731003a1c4150a149249f0238009eca6ed5c03aecf7e3e5aa3584006c8089`. Summary status: `recovered_requires_source_review`; exact law text and witness take precedence.

Accepted membership IDs: none. No source-hashed equivalence receipt or accepted recording contents are available locally, so no reuse is claimed.

Incomplete CPU work: Delivery package incomplete: two controlled branches are planning definitions only; no four distinct CARLA constructions, offline and compatibility proofs, saved measurement fixtures, or independent audit. Physical realization and legal outcome remain unverified.

Resume by resolving every statutory branch and exception against the law text; construct physical Native routes and controllers in the frozen cell; define measured channels and four distinct plans per selected case; run offline, compatibility, saved-only, comparison and independent audit proofs; set ready only after those proofs pass.

Update 016 status correction: missing case construction, candidate proofs and audits are actionable CPU work under START_HERE.md. This package is partial, with the frozen scope and listed resume actions preserved.

## 2026-11-23 source-bound diagnostic and exact unselected CPU bundles

Reviewed the exact law and witness. The covered device is a bicycle, electric bicycle or electric scooter riding on a sidewalk. The pedestrian priority duty applies to the encounter; the audible signal duty has a before-overtaking-and-passing order. No accepted membership is in the frozen assignment, so no original is reused. The unsupplied NRS 482.029 definition reference, municipal applicability, actual sidewalk and device class, and legal meanings of yield and audibility remain for independent review.

`sidewalk_meter.py` generates and measures four 600-frame, 20 Hz source-shaped diagnostic variants under `.runtime-work/c230266-sidewalk/`. It joins distinct rider and pedestrian identities, full sidewalk footprints, speed, ahead/behind pass brackets and microphone samples at the pedestrian. The detector threshold is an engineering test, not a legal cutoff. It rejects missing microphone source and reports no Native or legal finding. Proof: `sidewalk-meter-proof.json`, SHA-256 `96880cb6071ab9be744babc9b039c23ee9c447d1ef45ab69f58ba416760f5d5a`.

`case-plan.json` now separates signal-request variation (probe A/B) from pause-request variation (probe A/C). `native/road.xodr` defines an explicit sidewalk lane; `native/runner.py` checks frozen identity, 600-frame duration, four named cameras, bicycle blueprint filter, pedestrian-location microphone and controller requests. Three exact unselected inline bundles in `native-draft/` pass pinned `runtime.py offline` with four CPU tests each; hashes and commands are in `native-draft-proof.json`, SHA-256 `8a939b8a37f61d6499efb787da713e68a79453efee4c9dee3a8abb883d3b9257`. This is a CPU draft only.

Remaining CPU construction: implement original CARLA bicycle/pedestrian capture and source frame map, synchronized microphone acquisition at the pedestrian, source-bound finalizer, saved processing, positive/negative compatibility, exact fallback candidates, semantic proposals and independent acceptance/comparison audits. Native blueprint availability, actual mic capture, physical motion, audible sound and law findings have not been proven. Run scoped strict only after these are implemented.

## 2026-11-25 current-runtime selected diagnostic milestone

Implemented original Native bicycle/pedestrian source capture, four 600-frame camera streams, map/actor/frame readback and fail-closed live ALSA pedestrian microphone and rider signal paths. Original acquisition still requires the local Native host and verified physical placement; these CPU proofs do not assert it happened. The saved finalizer joins actor footprints, original RGB frame references, map context and 8 kHz microphone PCM with Native frame timing, preserving device-class, sound identity, physical and legal uncertainty.

All three exact bicycle probes now pass pinned offline, public positive/missing-microphone negative compatibility and recorded-only saved processing on current construction bytes. The selected draft manifest is `draft-selected-execution-manifest.json`, SHA-256 `7cb0eb3d559f2342f71fe1c977fd966edd7295978f057290ef9b2d2444014bc6`; per-case receipt and log hashes are in `selected-diagnostic-proof.json`, SHA-256 `1d8267926b9bd3ed196f78d0a78e69f4f806859ce76728666b23ed5dde3f1341`. The partial scoped checker exits 0.

Remaining CPU work: exact physical-risk fallback constructions and their proofs; canonical selected manifest with post-capture, semantic, delivery, physical/lifecycle and comparison audits; exact strict gate. Statutory electric bicycle and electric scooter alternatives remain explicit `alternative_pending`: the current exact Native asset is a bicycle, and no electric device asset has been source-verified. A bicycle diagnostic cannot be relabelled as either electric class. Keep result partial and make no original/physical/legal acceptance claim.
