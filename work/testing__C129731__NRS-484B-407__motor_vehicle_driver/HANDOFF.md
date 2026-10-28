# Handoff: testing__C129731__NRS-484B-407__motor_vehicle_driver

Status: **ready**, CPU capability preparation only. No CARLA or physical acceptance was run.

QA repair: the 120, 152.4 and 180 m sight probes now originate from native lane waypoints at exact arc-length stations on a 500 m curved road around turn station 250 m. Only original frames within 5 m of that station contribute a sight sample. The materialized offline runner no longer assumes a repository-relative runtime path. All three exact cases passed renewed preflight, offline and full compatibility with rebound receipts.

Exact cases: 3. All case-specific Core atom gates, bundled offline tests, actual analysis, native validation, Core/Lean conversion, rendering and final video decoding passed against a diagnostic synthetic fixture. Receipts and log hashes are in `execution-manifest.json` and `result.json`.

The diagnostic acquisition base is the current trial’s pinned three-frame source. Adapted counterpart/ray/landmark records are synthetic arithmetic and join probes; the straight road is not scene evidence. Source terms are mapped separately from supported Core atom IDs.

## Local runtime checks still needed

- native curved/crest geometry and 500 ft views from both directions
- actual U-turn completion and safe approach visibility
- four-camera framing, source duration and public-way status

Run the exact case construction with an operator-owned CARLA endpoint, inspect original native topology/landmarks/crosswalks and source video, then assess the unresolved legal facts. The current result makes no statutory determination.
