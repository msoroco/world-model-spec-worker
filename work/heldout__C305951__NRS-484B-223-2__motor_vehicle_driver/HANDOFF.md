# Handoff: heldout__C305951__NRS-484B-223-2__motor_vehicle_driver

## Frozen scope

Upon a highway which has been divided into three clearly marked lanes, a vehicle must not be driven in the extreme left lane at any time. A vehicle on such a highway must not be driven in the center lane except: (a) When overtaking and passing another vehicle where the highway is clearly visible and the center lane is clear of traffic for a safe distance; (b) In preparation for a left turn; or (c) When the center lane is allocated exclusively to traffic moving in the direction in which the vehicle is proceeding and a sign is posted to give notice of such allocation.

Cell C305951: three_lane_road / travel / lane_marking; actor motor_vehicle_driver.

## Full-text branch inventory for CPU construction

- Three clearly marked lane highway: extreme-left lane prohibition.
- Center lane exception (a): overtaking/passing with clearly visible highway and clear center lane for safe distance.
- Center lane exception (b): preparation for left turn.
- Center lane exception (c): center lane exclusively allocated to travel direction and posted sign.
- Compare center travel with each exception held or absent; no numeric safe-distance legal cutoff is given.

## Current checkpoint

Eight planned cases cover the extreme-left prohibition, center lane without exception, visible/occluded passing context, left-turn preparation, and center-lane allocation with and without a posted sign. `three_lane.py` requests actual markings, a passing actor, a sight-blocking occluder, turn route and allocation sign through an adapter; it measures original lane occupancy and checks source presence. Tests exercise feature creation and missing-source/fixed-condition rejection; `cpu-tests.log` SHA256 is `a14a836e617e577bea18de5ac6eee35d08fc837cbc2d50a4dad7f520a8e9ba96`. The sight and safe-distance judgments remain open.

Status remains partial. Concrete Native adapter, four-camera capture, exact runner/config/construction, three fallbacks per case, compatibility, saved processing, semantic proposals and delivery audit remain CPU work.

## Exact next CPU work

1. Independently split the original law into all applicable clauses, alternatives, exceptions and any explicit numeric boundaries; map each to source-backed reuses or exact comparison cases without changing frozen cell/actor scope.
2. Complete canonical semantic proposals, runner/config/construction, controller and four-camera plan, raw source acquisition, finalizer, measurement contracts and three tested risk-triggered fallbacks per selected case.
3. Run `.venv-cpu/bin/python runtime.py offline` and `.venv-cpu/bin/python runtime.py compatibility` for each exact case and fallback, plus `runtime.py process-saved` on retained synthetic sources. Implement and test rejection paths in independent delivery and comparison audits.
4. Update result.json with hashed logs only after proofs pass, then run `.venv-cpu/bin/python worker_check.py --assignment heldout__C305951__NRS-484B-223-2__motor_vehicle_driver --complete --require-delivery-ready`.

## Dependencies and limits

Use the pinned runtime. CARLA, SQLite and canonical source recordings are unavailable in this CPU repository; those do not block the listed CPU preparation. The accepted summaries are retained as historical source evidence.

## Current CPU proof

Run `.venv-cpu/bin/python -m unittest discover -s work/heldout__C305951__NRS-484B-223-2__motor_vehicle_driver/tests -v` and `.venv-cpu/bin/python worker_check.py --assignment heldout__C305951__NRS-484B-223-2__motor_vehicle_driver --complete`. Strict readiness still fails while this package is partial.

## Exact C305951 primary source checkpoint (2026-11-12)

The C305951 right-baseline travel-cell construction (`construction.json` SHA256 `cbdbf81d8e0efb272f281702f176bd1c8b01c952bfc44846e2886d52588ca70c`) selects a connected, ordered three-lane route, retains original ego-body polygons at 20 Hz, and captures four named cameras for 8 s. The C304406 source implementation was adapted to this cell and assignment identity; its original C304406 case recordings and proof receipts were not reused. The root config covers this assignment’s eight selected case IDs.

Exact offline passes (`right-baseline-offline.log` SHA256 `ca32b970f69c58fd9264915622698210e89b72da2bf765775c2c248cded4350a`); positive and missing-three_lane_frames source compatibility passes (`right-baseline-compatibility-receipt.json` SHA256 `71f8c36d894e19a4d6e3697e05b522876a29f5233e817bfca3f64188dccf6daa`). A clean source-only saved attempt at `.runtime-work/c305951-right-baseline-saved-attempt1` processes with `passed=true`, `missing_evidence=false` (`right-baseline-saved.log` SHA256 `b34dfd387c704b457a0f9dc8b6f4712c091e161cfa3557a397c4256e28f06ac1`). The independent audit binds five original source hashes, exact frame/case identity and measured right-lane occupancy (`right-baseline-source-audit.json` SHA256 `ee5f28bb54a3b6d8ebe70191038a0e029b88eca209446d25d4650e7e0d5fa126`). The 19-test suite passes (`cpu-tests.log` SHA256 `a3e2154c466436043c3db1b468efd42563e4363148d8d38fe3951775f0a76ff1`).

The first process-saved attempt used the compatibility workspace directly and retained a derived three-lane channel; it returned `missing_evidence=true` with `Retain prior derived three-lane channel`. The clean source-only attempt fixed this and is the cited proof. Status remains **partial** pending the seven other exact cases, fallbacks, semantic stages and audits. No physical or legal acceptance is claimed.

### Extreme-left continuous-occupancy CPU checkpoint (2026-11-12)

The second exact `left_travel` construction (`construction-left-travel.json` SHA256 `7ab28642b8f4fea538b80469e215fc7e2cba38a87496a4648ebb3252a9d83c82`) keeps the physical role `extreme_left` and records framewise original body overlap on the marked three-lane map. Exact offline4 passed (`/tmp/c305951-left-travel-offline4.log`), positive/missing-source compatibility2 passed (`.runtime-work/c305951-left-travel-compatibility2/compatibility.json`), clean saved processing2 passed with `missing_evidence=false` (`.runtime-work/c305951-left-travel-saved-output2/v0001/processing.json`). The independent source audit passed in `/tmp/c305951-left-travel-source-audit.json` against the first source version and must be rerun against saved attempt2 before return binding. The compact diagnostic is 1,463,814 bytes; recipe SHA256 `30353c685634dddd75103e6f8f1b47734cf3b290e1318039f61f12a65214198f`. These source outputs are not yet retained return receipts and do not establish physical/legal acceptance.

The current left-travel proof is now returned: `left-travel-offline.log` SHA256 `e598c3d64f61addf5a83816902540526aa43932df184d323e7ae2c6710e31b7f`, `left-travel-compatibility-receipt.json` SHA256 `bb723844099a33da73ef0d19f42a5818b87159536d0ba2f112acc2a243e8fb74`, `left-travel-saved.log` SHA256 `8a6594ac9ab5b796055f0bc67d8fb818d80f9f15d44a7c4b4d51e52d062f71ea`, and `left-travel-source-audit.json` SHA256 `10e7de38893fe1d84fe433bbb39b6bbc6eeab96ffa6f8fd7259c37e8a03b6175`. Current independent audit source `audit_extreme_left_delivery.py` SHA256 `ef7232967a82b06c7232d37858e1fe191084111800ad35b0e700bd6cae14d30d` confirms exact saved case, five original hashes, framewise extreme-left overlap and no physical/legal acceptance claim.

### Canonical C305951 semantic source checkpoint

The exact relevance batch/cell, shared NRS 484B.223(2) template, five value-free qualitative observable proposals, travel-cell bindings and canonical baseline plus eight selected cases are indexed by `proposals/semantic-index.json` SHA256 `48be150d3660603148ac3946c122d971552ee12f4acb629594f98bfd239a119f`. All stages pass the pinned stage validators in `/tmp/c305951-build-semantic.py`; the original law quote and unknown physical/legal judgments remain intact.

### Unexcused center-lane travel and right-versus-center comparison

`center_no_exception` exact construction SHA256 `c213e56f79f4f3e04447f5ef8c4c4d57c8ffb296e3d3cba791d6a1dc5b9a2e75` passes offline (`center-no-exception-offline.log` SHA256 `fd449fc5bdaf8f9289e93e9bdffbea44616b18ca974bdb022013d859708df58b`), positive/missing-source compatibility (`center-no-exception-compatibility-receipt.json` SHA256 `f0b216253e679c0ed23178fef34728aacfc16255bba532f28f33b893eba88b9a`), and source-only saved processing with `missing_evidence=false` (`center-no-exception-saved.log` SHA256 `85b37c90db29cf54215a25a320004de7cd5b449a1a97f78a06c20c8b605e00c2`). The independent original-source audit SHA256 `d4247303f812b26d4140939dc051a5e66a76df6276be4d2578742175984c5e26` binds case ID, five originals and center-body overlap. The right-versus-center comparison SHA256 `800c335afe45532742656fb2d92e547657a1de937650e7bde62cef7964e40476` confirms common map, frame plan and source conditions while isolating right versus center occupancy. No legal verdict follows from these synthetic source proofs.

## Center passing clear exact checkpoint

`center_pass_clear` construction SHA256 `a09fa3ba7ff3b70fa69cc57653b85eba9dd775a50c820c08a21c21e433de1a5b` passes exact offline (`c1eac33e4ff5276c58114401ba2c609852173b1a94b78cb0df32c2ffc2e44d0a`), positive and missing-passing-source compatibility (`eefabbcd9f72dc3fa505b3515ddc992462448e18721179b293966971138e9639`), and clean saved processing with `missing_evidence=false` (`1bb5471826fc20d77b2feaff76b07e4d12d577c5770487ad88e6bbe09b0f7043`). Independent original-source audit `1d27edc945cbac8ebd905530348cccd04fa524d92b42f23a4bff2f63bb5fb38e` verifies six retained originals and center engineering clearance. Fixed-source comparison against `center_no_exception` `9e534c7bfcd1273519418963a6706616633faf8bc5ebdbef9a675cb4ba5c7055` isolates the added passing target. These are synthetic source checks; physical sight and legal safe distance remain unjudged. Four other selected cases, fallbacks, delivery acceptance and physical preparation remain CPU work; status stays partial.

## Center passing occluded exact checkpoint

`center_pass_occluded` construction SHA256 `2ba9ed1d5f2e752a5a86acb37d62903564e73efbcf971c77ed4666e09a8d606d` passes exact offline (`c1eac33e4ff5276c58114401ba2c609852173b1a94b78cb0df32c2ffc2e44d0a`), positive and missing-occluder-source compatibility (`a19d0ff9a553ff6f1f7e64e643d53a5219f962af09d9463cc8163e6c64dde83b`), and clean saved processing with `missing_evidence=false` (`44d45e250b3f34c238a85c7605d59028d4296016d6ff9a29fdcd21b9f3ac01dd`). Independent seven-original source audit `899bc46208e5bf87f18b64cfa5ad8fefabf78c600a05f7ac11adfbbf4b34bb9f` and fixed-source clear-versus-occluded comparison `1c263c93bbb74044847be4672b96fdefa3928306160ab9f3b27798fd5a52d438` pass. The latter isolates the added occluder original; actual line-of-sight occlusion and legal safe distance remain unjudged. Three selected cases, fallbacks, physical protocol and delivery acceptance remain CPU work; status stays partial.

## Center left preparation staged checkpoint

`center_prepare_left` returned construction SHA256 `901bd7ecaa06a18e7e7f39525a404ac41e49d0d0393ef6d76276bc81d4041d10` passes exact offline, positive and missing-left-turn-source compatibility, and clean source-only saved processing with `missing_evidence=false`. Independent seven-original audit and center-versus-left-preparation comparison pass in ignored `.runtime-work/c305951-center-prepare-left-*`. Their receipts are not yet returned because the 10,200-file package cap is near. Physical turn completion and legal judgment remain unconfirmed; status stays partial.
