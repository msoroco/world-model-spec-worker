# training__C230247__NRS-484B-307-12a__motor_vehicle_driver

Status: partial. The exact text of NRS 484B.307(12)(a) grants a driver facing a downward green arrow permission to drive in a lane over which that arrow is shown. The clause does not itself forbid another lane. The paired red-X provision is a separate assignment.

The frozen snapshot lists zero accepted recordings, so no accepted evidence is claimed reusable. The two planned comparison cases remain unselected.

## New CPU work

- `native/lane_arrow_meter.py` requires 600 original post-tick frames at 20 Hz, Native indication state, signal inventory authority, overhead mount, governed lane, driver yaw, proposed lane and occupied lane. It rejects missing source identities and provenance. `native/prove_lane_arrow.py` tests a facing green arrow, different proposed lane, reversed orientation, red X and nine missing-source fields. Proof log SHA-256: `fa72a8b5078557b973ee82c362e8a2765bdf37fa8a5c099a7618289983dff265`. These are source-shaped diagnostic packets, not actual CARLA observations.
- `native/measurement-contract.json` maps the frozen observation terms to source fields and records the permission boundary.
- `native/road.xodr` proposes two highway driving lanes and a dynamic overhead signal (id 100) over lane -1. `native/draft_runner.py` contains exact 600-frame same-lane and other-lane controller requests and a Native post-tick source-row interface. The OpenDRIVE signal is a proposal; official authority and actual indication remain unverified.
- `native/build_drafts.py` built two exact unselected four-camera, 30-second bundles in `draft-same_lane/construction.json` (SHA-256 `1c5ec976a280efe052d095067bcfaf0970b2c96f57ed088069f64d8b3adcc5f6`) and `draft-other_lane/construction.json` (SHA-256 `c5f0dcc3f02d27bb3d6f972634591c6e28769f236e052696cc1772bf39f2668d`). Both passed pinned `runtime.py offline`. Logs: `de60e0abaddac6040808275543a43f42d2c8e28e663a11bab611ba1ebe9c0971` and `9f4c8c5c52db93e99b73029ab8906a30737359a08b9374ff27bce4877be4610d`.

## Remaining CPU work

Implement selected CARLA orchestration with signal-state readback, map authority verification, actor spawning and lane tracking, frame-map capture for all four cameras, saved-only finalizer, source-bound compatibility positives and negatives, semantic proposals, physical-risk fallback constructions, and independent delivery/comparison audits. Promote no draft without those exact proofs and the assignment-scoped strict gate. The local GPU operator must still verify actual indication, lane occupancy and pixels after CPU preparation.
