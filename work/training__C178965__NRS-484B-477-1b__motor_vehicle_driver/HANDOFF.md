# C178965 / NRS 484B.477(1)(b) handoff

Status: **ready** for delivery preparation. The exact assignment-scoped strict CPU gate passed on 2026-11-25. No original Native recording or legal verdict is claimed.

## Selected cases

| Case | Primary construction SHA-256 | Fallback construction SHA-256 | Current-runtime compatibility |
| --- | --- | --- | --- |
| controlled_1 | `59f0e190b704adc7bfc26333e1620e135a5a1941f3c99fba8467c2bd8f761cbb` | `2b56b69bcfc13481c86cbb4fd3135a806e20b4f67b9ec3282e16205329e1c635` | primary and fallback passed |
| controlled_at_10 | `afa55c4324d45b4343459f4129a0671c3db81a64b29ae732e43a792111277190` | `6d5e3d68d0a4a6dceab7eb655efb62d385331dfa6927a3f792433cec21adcd21` | primary and fallback passed |
| controlled_2 | `0eb99d74b6ddba49e6b99f6168351d58389d264e1f179155e41fe70fa0df13ec` | `2de6c4dc0d5395046413ef991cd917e3e04a840caee8249ecf9ab398b8ecf178` | primary and fallback passed |

Each selected case also passed pinned offline proof, a missing-case-source negative compatibility check, recorded-only saved processing with original fixture sources preserved, and positive/negative delivery-audit CPU checks. The semantic delivery chain, execution manifest, and compatibility receipts validate. Synthetic 600-frame parking completion, missing-evidence and lifecycle-order probes passed for all three cases. The comparison audit isolates the authored free-width variable at 3.9 m, exactly 3.048 m, and 2.4 m; this remains a diagnostic measurement, not a legal judgment.

## Key bound files

- [Execution manifest](execution-manifest.json): `e5c18df281b040390e80822b6d08f24fae61df3234444a2947197dccd1b3cf60`
- [Semantic index](proposals/semantic-index.json): `82880bf80238b787e4c69ecf987af9e786e6d0499e2fa859b6c3441671b2c6f5`
- [Diagnostic comparison audit](comparison-audit.json): `8ca86984d760508a15c6917df033d2d0cd199b58ccb4e23828f39279444bdc98`
- [Source branch review](source-branch-review.json): `c6b13ee27223de5e17d0acbc24a95ec4a1594d38c4c816de753207f632535333`
- [Result](result.json): `97e8af22a537128275051edab53b934186e8e8fbb020599c640752002a1aa5ff`

## Original-source delivery checks

The local Native owner must verify all 600 original frame/time joins and four original pixel streams; subject and distinct other-vehicle footprints; actual parking approach and stable rest; measured available width for the full rest interval; and an independently source-hashed site packet proving a qualifying "other alley," jurisdiction, and local ordinance effect. Free movement and stop/stand/park legal classification remain for independent review. The selected frozen cell is park; stop and stand are recorded as textual alternatives, not silently claimed as exercised. If the primary actor spawn or pavement intersection fails, select the documented height-only fallback and rerun the same source checks.

## Reproduction

```sh
export SCENARIO_PIPELINE_OUTPUT_ROOT="$PWD/.runtime-work/c178965-owner"
export TMPDIR="$PWD/.runtime-work/c178965-owner/tmp"
.venv-cpu/bin/python worker_check.py --assignment training__C178965__NRS-484B-477-1b__motor_vehicle_driver --complete --require-delivery-ready
```
