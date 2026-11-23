# testing__C227824__NRS-484B-307-8b__pedestrian

Status: partial CPU construction checkpoint. Six cases and five comparisons are planned; no recording or physical acceptance is claimed.

Exact law: NRS 484B.307(8)(b) — Where the signal is a steady red signal alone: Pedestrians facing such a signal shall not enter the highway, unless permitted to proceed by another device as provided in NRS 484B.283 [NRS-484B-283-1d1, NRS-484B-283-1d2, NRS-484B-283-1d3, NRS-484B-283-1d4].
Assigned branch(es): pedestrian_highway_entry.
Cell: C227824 (road, cross_road, traffic_light); actor: pedestrian.
Frozen accepted recordings reviewed at metadata level: 0. See case-plan.json evidence_review for exact IDs, source paths, hashes, demonstrated metadata and limits. Metadata does not establish law-specific coverage.
Judgment range entries inventoried for this exact law and actor: 0. Bounds are training coverage targets, not legal cutoffs.

## Next CPU actions

1. Source-review the exact public highway extent, official signal governance and NRS 484B.283 permission conditions against a candidate map. The authored geometry alone cannot establish public dedication, lawful device authority or actual pixel visibility.
2. Build exact, source-hashed Native scenes for the six planned variants in `case-plan.json`, with one traffic signal facing the pedestrian and an independently inventoried other device. Bind the entire highway boundary, not only the traveled roadway edge. Use `walker_control.request` for requested entry or waiting and retain original walker body vertices, signal state, device indications, countdown, four video sources and canonical frame joins.
3. Connect the saved-source `saved_entry.build_report` to canonical Native result finalization, then implement semantic proposals, independent delivery audits, exact offline and positive/negative compatibility proofs for every case. Add a measured-trigger fallback only if a concrete physical risk calls for an alternate construction.
4. Run `.venv-cpu/bin/python worker_check.py --assignment testing__C227824__NRS-484B-307-8b__pedestrian --complete --require-delivery-ready` and repair every failing gate. Keep original inputs and runtime frozen.

## 2026-11-23 CPU construction checkpoint

The exact law prohibits new highway entry while facing a steady red signal alone, subject to another device under NRS 484B.283. The exported 283(1)(d)(1) WALK and (2) flashing countdown clauses can potentially permit new entry, while (3) flashing without countdown and (4) steady hand distinguish new entry from continuation by a person already lawfully inside. This plan records indications and source events; it claims no legal verdict. The frozen accepted inventory has zero recordings, so the assigned red-entry branch is not evidenced by existing accepted material.

`case-plan.json` now names six exact variants: `red_no_device_entry`, `red_no_device_wait`, `red_walk_entry`, `red_countdown_entry`, `red_flashing_no_countdown_entry`, and `red_steady_hand_entry`, each prefixed by this assignment ID. Five comparisons isolate requested movement or the separate pedestrian-device indication while keeping the facing red signal and mapped highway boundary fixed. Each case carries a physical risk assessment; no fallback is claimed or bundled yet.

`entry_measurement.py` measures the first full-body highway-boundary contact from original synchronized frame rows, snapshots the facing red signal and all inventoried other devices at that frame, and reports original-frame full-body clearance relative to countdown zero. Missing signal, device inventory, countdown, unordered frames, and a body already inside the highway on the first sample fail closed. It does not infer legal permission or physical visibility. `walker_control.py` issues a lazy CARLA `WalkerControl` request toward a reviewed route target or an explicit zero-speed wait; actual motion remains unverified.

`.venv-cpu/bin/python -m unittest discover -s work/testing__C227824__NRS-484B-307-8b__pedestrian/tests -v` passed 12 tests; retained log and SHA are in `result.json`. The tests exercise boundary contact, separate device snapshots, countdown ordering, missing sources, entry direction, waiting, invalid requests, accepted fixed-condition comparison pairs, and rejection of changed boundaries or missing entry/device evidence. `comparison_audit.py` independently checks fixed source identity, the facing red at first entry, movement or separate device isolation, and rejects absent original-frame evidence; it makes no legal or physical acceptance claim. `.venv-cpu/bin/python worker_check.py --assignment testing__C227824__NRS-484B-307-8b__pedestrian --complete` passed as a truthful partial checkpoint. No exact Native construction bundle or source-bound compatibility proof is claimed, so status remains partial.

The focused strict gate and complete-batch strict gate both exited 1 at `Preparation acceptance failed: partial/missing packages remain`; logs are `.runtime-work/c227824-strict.log` and `.runtime-work/full-strict-c227824.log`. The top-level CPU unittest suite passed 3 tests. Resume by binding the six cases to an exact map and acquisition sources, then completing source-bound saved processing and proofs; do not promote this checkpoint to ready on the strength of these focused tests.

## 2026-11-23 saved-source continuation

`saved_entry.py` now reads the exited attempt's source-hashed scene, body, signal, device, video-frame and four-camera join packets, plus the four declared video files. It rejects missing or changed source hashes, incomplete packet groups, frame/time or case mismatches, and absent camera joins before calling `entry_measurement.measure_entry`. Synthetic fixtures are explicitly labeled; the resulting report leaves `actual_pixels_verified`, `physical_acceptance_claimed` and `legal_verdict_claimed` false. This is saved-source measurement, not canonical Native result finalization or a decoded-video audit.

The focused suite now passes 16 tests, including positive source joins and rejection of changed hashes, missing devices and misaligned camera frames. `cpu-tests.log` and the current SHA are bound in `result.json`. `.venv-cpu/bin/python runtime.py preflight`, the focused partial `worker_check --complete` and the repository 3-test suite pass. The complete-batch strict gate was rerun after this edit and exits 1 at `Preparation acceptance failed: partial/missing packages remain`; its retained log is `.runtime-work/full-strict-c227824-saved.log`. The initial test attempt used a temporary path one directory above the workspace and failed read-only; the fixture path was repaired to the repository's `.runtime-work/`, and the full suite passed. No output was written under `runtime/`.

## 2026-11-23 original-signal acquisition continuation

`native_signal.py` now binds the exact original route-facing traffic-light actor and any separate pedestrian-device actor from a source-hashed, explicitly complete device inventory. It rejects a mere CARLA Red state without official route and sole circular-head metadata. Its `configure` requests and reads back red alone; if a separate device is planned, it requests and reads back WALK, flashing hand with countdown, flashing hand without countdown, or steady hand through an explicit pedestrian-indication driver. `sample` captures original frame/time signal and device packets, including countdown readback, for `saved_entry.py`. Missing reviewed authority, mismatched route, absent device driver, changed actor IDs, nonred frames and unreadable countdown fail closed. This does not prove actual pixel visibility or the statutory permission condition.

The focused suite now passes 20 tests, including signal binding/configuration/sampling calls and negative authority/readback tests. The current log SHA is bound in `result.json`. The scene asset and its complete authority inventory still require source review; a custom pedestrian indication driver is an explicit CPU implementation dependency for the device variants. Neither is classified as an external blocker while exact Native scene and acquisition integration remain worker-owned CPU tasks.

## Proven checks and dependency boundary

`.venv-cpu/bin/python runtime.py preflight` passed; `.venv-cpu/bin/python worker_check.py` passed static checks; `.venv-cpu/bin/python -m unittest discover -s tests` passed 3 tests. These are repository checks, not this assignment's delivery proofs. CARLA is needed only after the CPU package is ready, for actual motion and video verification. No external blocker has been demonstrated for the remaining CPU work.

Frozen witness review: 1 entries retained in `case-plan.json.witness_review`, including conditional context requirements and source indices. No exported review-context/review.json is present.

Latest complete-batch strict gate: `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python worker_check.py --complete --require-delivery-ready` exited 1 at `Preparation acceptance failed: partial/missing packages remain`; log `.runtime-work/full-strict-c227824-signal.log`. The 20-test focused suite, CPU preflight and focused partial check pass. Resume with exact source-reviewed scenes, Native packet writer integration, canonical saved result and source-bound proofs.

## 2026-11-23 original tick packet continuation

`native_packets.py` now samples the original CARLA walker world bounding-box vertices, uses their conservative XY envelope, joins original signal/device readback from `native_signal.py`, requires all four camera image frames to equal the same world snapshot, and writes the five source packet streams expected by `saved_entry.py`. `PacketWriter` permits only a fresh private `.runtime-work/` attempt, enforces increasing frame/time and exact case/time joins, and refuses existing packet files. `source_hashes` binds completed packet, scene and video bytes after encoder exit without making a capture-seal claim. The caller must still run the actual camera recorders, world lifecycle and runtime Native sealer; this helper is a construction component, not an end-to-end Native runner.

The focused suite passes 23 tests. A mocked original tick sequence was written to a private attempt and then read by `saved_entry.build_report`; first highway entry was measured at the intended source frame. Negative tests reject stale camera frames, duplicate ticks and reuse of an existing packet file. The fixture uses placeholder video bytes and remains explicitly synthetic; it does not prove decoding, physical motion or pixel visibility. The current test log SHA is in `result.json`.

After the packet-writer change, the 23-test focused suite, CPU preflight and focused partial `worker_check --complete` passed. The complete-batch strict gate exited 1 at `Preparation acceptance failed: partial/missing packages remain`; retained log `.runtime-work/full-strict-c227824-packets.log`. C227824 remains partial until an exact Native runner, source-reviewed scene/map, canonical result, proposals and required proofs exist.
