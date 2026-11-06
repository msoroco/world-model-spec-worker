# NRS 484B.283(1)(a), C111256 CPU draft

Actor: `motor_vehicle_driver`; frozen cell: intersection / travel / crosswalk. The exact frozen source and case bindings are in `case-plan.json`; seven source-topic branches are inventoried in `statutory-review.json` and remain pending in the shared matrix.

The Native proposal authors a marked uncontrolled crosswalk, northbound ego route, directional-half pedestrian crossing, capture channels and four-candidate engineering plan. `witness_1` yields before the ego-half crossing; `witness_2` overlaps the pedestrian conflict. `exception_1_1` and `exception_1_2` share ego/pedestrian trajectories and vary only a synthetic blind-person/white-cane declaration. This declaration is not a physical cane or legal eligibility proof.

The primary plus three distinct fallbacks change lookahead after measured cross-track error >0.45 m, increase yield-clearance margin after measured clearance <1 s, and widen overview FOV after measured body/crosswalk pixel margin <40 px. Trigger values and exact source hashes are bound in `native/engineering-plan.json`.

Proofs: 5 Native unit tests; independent Native CPU and statutory audits; 480-frame saved processing for all four cases with four decoded videos each and missing-road-geometry negatives; 16/16 exact pinned offline bundles; 16/16 synthetic v1 positive/negative portable package diagnostics; independent package and controlled comparison audits; four case measurement contracts validated against selected source dispositions and finalizer methods. These are CPU synthetic diagnostics only.

Audit hashes:
- `draft-execution-manifest.json` SHA-256 `11a4a47ad2e7d3fe4ed23c9d520834bdb5088e06fdf409c2648d99dac155f8c3`
- `draft-offline-summary.json` SHA-256 `d8e5d0530f43258ecc3af3fc0f66bbc71ceb2d22747895395f05b54416fe7595`
- `package-probes-summary.json` SHA-256 `299efd65eabcb8bbb7402a11f827f349be725eef5a6674871a0897f65eafca23`
- `package-probes-audit.json` SHA-256 `d244d79ddf10577c1683051224c8546305e7ef94e19de8655adbdc7304912d05`
- `synthetic-comparison-audit.json` SHA-256 `e3847cefbaec014caafc5317dace8bc627c2f3ece44cd390daf99245a9e80ac1`
- `native/cpu-audit.json` SHA-256 `837dc75bc180473c643e1bd61ff4153c0fcfc8b5d45af78d7814aad2d63a87e7`
- `native/saved-fixture-proof.log` SHA-256 `a44c798cffc53aa00571429f406b453090feda677c1950ad56d927b2d3f9c1e6`
- `statutory-review.json` SHA-256 `bc5debb1fc5e468ca9b2856c916791fccd54492e4c5987ec6161328259650d78`

Unclaimed source alternatives: cited NRS 484B.287 crossing restrictions, NRS 484B.350 school pedestrian lane, opposite-half near-danger crossing and one-way highway-half definition. Exact NRS 484B.290 physical cane/eligibility construction, original camera pixels and real pedestrian behavior are also unverified.

Status: blocked, unselected, zero delivery cases prepared, zero accepted recordings. Strict selected v2 CPU delivery proof, independent selected delivery audit, canonical selected commands and ordered GPU queue row remain to be built. The physical white-cane and eligibility gap is worker-owned; the synthetic declaration does not resolve it.

Reproduce from this assignment directory: `python3.11 native/test_native.py` from `native/`; `python3.11 build-draft-candidates.py`; `python3.11 run-draft-offline.py`; `python3.11 saved-fixture-proof.py`; `python3.11 run-package-probes.py`; then `python3.11 audit-native-cpu.py`, `python3.11 audit-statutory-review.py`, `python3.11 audit-package-probes.py`, `python3.11 audit-synthetic-comparison.py`. The Native runner is a proposal; no CARLA run was made.
