# C42417 turn-signal distance CPU checkpoint

Status: **partial**. Exact authored requests and unselected offline constructions pass CPU diagnostic checks. Native source readback, four original cameras, selected compatibility, actual saved processing and independent audit remain unproven.

Selected statutory branch: NRS 484B.413(2), continuous right-turn signaling for at least the last 100 ft traveled in a business district, regardless of weather. Other-area 300 ft, residential-area, left-turn, other-course-change and hand-signal alternatives remain to be constructed/audited. A command to light an indicator is not proof of visible lamp onset.

## CPU construction and proof

- `native/signal_distance.py` (SHA-256 `9ccab0309131bc156c86fe0b043df8d5d75f4fdf7ec6b5c946d144e7735389d3`) generated two exact 600-frame, 20 Hz, 30-second authored requests at 10 m/s with a turn at frame 300. The indicator begins at frame 220 in A (40 m continuous distance) and 260 in B (20 m). Both fix business district and rain; weather does not change the rule. `native/signal-distance-proof.json` SHA-256 `31bad54633b5a3d0de04617aca004350277f4bc8d269d22583a49f6a73206ef2` measured those distances and rejected a lamp gap, missing lamp source, wrong district and forged provenance. These are request diagnostics, not Native evidence.
- `native/build_draft.py` SHA-256 `fe35a071ac0ec0a27e7fca765f2bb14345ef760c4537252457c770339a5da09d` built exact unselected offline packages. Construction hashes A `b4c190b561a7c90d2ac3958e25d1c3aa20cee44ef246a487da14bd5424f54b62`, B `46b5d0e60cb23da6d386962a6a2cec283ba547d3ce205cf4a5a73eb1fa678b14`; draft manifest `fb95a9e5c416fe384cce3022b7a805ff687a8ec17bcbcc28a81251f2fd89feed`.
- `runtime.py offline --manifest work/<assignment>/native/draft-manifest.json --case <exact-case-id> --output .runtime-work/c42417-offline-<condition>` passed for both exact cases with `simulation_started=false`. Returned logs A `177113a11b0946d7f7a812eaf00721f7307478eefecc1fa6ef5df708f673c861`, B `c6918e8b6f45b7355e3abbbd98fcdce300a1573e9336402017c67b23fb4914a3`.
- `native/measurement-contract.json` SHA-256 `a6cf7e49b3ebf14f8f30d6f74ba8e21a239f713c08548a3ab21f1aa5fb32370d` maps the eight observation terms to original source requirements and records both area thresholds.

## Worker-owned remaining work

Build Native district geometry, ego right-turn controller, source-observed indicator state, original path/heading readback and four camera captures. Establish actual continuous signal distance from observed onset to course-change onset. Implement selected primary and risk-based fallbacks through offline and compatibility; run actual saved positive/negative processing and independent comparison audit. Add required statutory alternatives. Keep partial until scoped strict delivery passes.
