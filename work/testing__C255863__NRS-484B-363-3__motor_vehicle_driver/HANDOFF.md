# C255863 NRS 484B.363(3) checkpoint

Status: partial. The selected school crossing-zone U-turn and five exception controls are implemented in `school_uturn.py`: no children, school not in session, outside the half-hour operation interval, operational beacon not flashing during class, and inactive sign without operational beacon. Construction creates vehicle and child actors and schedules a reversal path and beacon. The finalizer requires 900 original frames at 20 fps, stable identities, child locations, independent source hashes, zone occupancy, and a measured heading reversal. It leaves U-turn legality and children-presence interpretation unset.

Source boundary: crossing-zone designation/extent, nonadjacent school property, pupil route, independent school calendar and operation/class times, local clock, children identities/locations, beacon configuration/state and sign instruction are separately required. The 150-degree heading span is a physical realization probe, not a legal U-turn definition. No accepted exact recording exists.

Focused tests, pinned CPU preflight and scoped static check pass. Exact scoped strict fails on truthful partial status; see `cpu-strict-check.log`. Successful receipt commands and hashes appear in `result.json`.

Remaining CPU: canonical runner/config/camera capture, source-shaped positive/negative compatibility, semantic proposals, saved-only processing, and independent delivery/comparison audits.

## 2026-11-26 source-gated school timing and comparison checkpoint

`school_timing.py` derives the exact statutory half-hour interval from offset-aware original schedule timestamps. It requires independent calendar, operation and class schedule, clock, beacon and sign hashes. It verifies the operational speed-limit beacon has at least two yellow lights capable of alternating flashes, and distinguishes device state, class hours, sign instruction and school session without a fabricated legal conclusion. `school_uturn.py` binds those derived states to each of the six case variants, requires 64-character source hashes, and checks Native beacon readback with cleanup on mismatch. The 900-frame reversal check uses frame-relative intervals; the 150-degree probe remains an engineering realization check, not a legal U-turn definition.

`comparison_audit.py` checks all five exact baseline controls against complete original 900-frame packets and fixed crossing-zone geometry, route and source bindings, rejecting missing or changed evidence. `gpu-queue-proposal.json` lists six exact cases and five comparisons with pinned prepare/execute/accept command order. It is unbound and not dispatchable. Eleven synthetic CPU tests pass; runtime verify, preflight and scoped partial check pass. The exact scoped strict check exits 1 on partial status.

`source_audit.py` confirms the immutable export contains zero accepted metadata and none of the six required source classes: reviewed school crossing-zone site/extent, school calendar, operation/class schedule, local clock, beacon/sign survey, and original Native capture. The conditional witness and cell label do not establish the actual school schedule, device operation, child locations or physical U-turn. To resume, supply reviewed original source packets with hashes, bind the construction to a Native site, create current-hash selected manifest and semantic proposals, then run offline/compatibility/saved/delivery/comparison proofs and scoped strict. Actual CARLA motion and visual quality remain later local checks. Status remains partial.

| Current file | SHA256 |
| --- | --- |
| `school_uturn.py` | `bd20ef0466b0d9b543d7581b876fc952a66a7827d78752f330284f4a65d00ae0` |
| `school_timing.py` | `e99472cf5c02d81deef88ccec5569cf4f454e28b863cc5da03dca73201fd5010` |
| `comparison_audit.py` | `ad53cf9bf1921c7eccce58c8e5844fb6c7db64a234852ce48c9e8c4d31097d3d` |
| `source_audit.py` | `50504c985e80a72b43174bfda2a17f9561612c2a6929d31f5532934bbd44f045` |
| `build_queue_proposal.py` | `477f4edfec9a01e84cfba31249fb0d61d8227817cda32207050cca795df018ec` |
| `case-plan.json` | `dd586fef64ed9409877381d515c0e1058fe6a24a362f34ed287f91f8bb611a7a` |
| `gpu-queue-proposal.json` | `0a64cd45d9dc7866cadd7ddc74871b9e9008dd763e186c6e10ee4d0cf1258748` |
| `cpu-tests.log` | `ea3f028fd13eca08c7a8b0fa82fe028e09ed14bdfb79d80ea3df8d098e8fc5d9` |
| `cpu-verify.log` | `e63dee921a6e4bdca8993964e3d5772efd51499fef90189bd29062aa42049c8d` |
| `cpu-preflight.log` | `524dd3b8eca52867d7eaa871e6fb377146df4a6d5765d42d915cf0dc0a428925` |
| `cpu-source-audit.log` | `52f45b65e2f42850f832c9511938f0088c59b07e5f776b76a416f960ca991176` |
| `cpu-static-check.log` | `6f2bebff75b45f3e09e157fd3e86a3385ba639e52d52d0e141c19e48c8e0ee91` |
| `cpu-strict-check.log` | `0d28089dee3f920ecd20a6ba1cea1530562eeb871c292d0f8a76c869d4230638` |
