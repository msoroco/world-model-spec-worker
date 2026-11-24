# NRS-484B-330-1 at C183370

## Current CPU construction checkpoint

`native/measure_flagger_response.py` now reads hashed temporary-zone geometry, 600 contiguous 20 Hz flagger indications and 600 joined motorcycle/moped rows. It measures signal duration, stop-line crossing time, and the indication at crossing. `prove-flagger-response.py` retains two synthetic traces with the same stop indication at frames 1100–1299 and release at 1300. The hold probe crosses at frame 1350 after release; the moving probe crosses at frame 1200 while the stop indication remains active. Two positives and six negatives (changed source hash, absent governing flagger, signal/vehicle frame gap for each) pass. Proof SHA-256 `ef351f5965beb3ee0384a7cf65384662f3aed37a07a31ec4433b7265c3e676de`.

`audit-flagger-response.py` independently checks frozen law terms, retained source hashes, raw joined rows, fixed signal policy, response motion and crossing order. It passed; audit SHA-256 `06ca3868fdfcd4ed98896897f0f56b6abe54917f91054529c939f17ac62c6e75`. The frozen witness is conditional and calls for independently establishing flagger authorization, actual signal governance and visibility, designated temporary-zone status, supported paved-shoulder-adjacent route, and a qualifying motor-powered motorcycle or moped with operator control. It also cautions against inventing a response deadline; this diagnostic measures event order without one. The synthetic fixture does not establish those administrative or visual facts, Native motion, selected delivery, accepted evidence, or a legal verdict.

Verification commands: `.venv-cpu/bin/python work/training__C183370__NRS-484B-330-1__motorcycle_or_moped_operator/prove-flagger-response.py` and `.venv-cpu/bin/python work/training__C183370__NRS-484B-330-1__motorcycle_or_moped_operator/audit-flagger-response.py` exit 0. Pinned `.venv-cpu/bin/python runtime.py preflight` exits 0; `current-preflight.log` SHA-256 `71c454356dc81c8d245a58947f9d765fda0f6739dabf20b6f0009d3a046b4b59`. `.venv-cpu/bin/python worker_check.py --assignment training__C183370__NRS-484B-330-1__motorcycle_or_moped_operator --complete` exits 0; `current-scoped-complete.log` SHA-256 `21c4b4eb2155e19d2b3a8fcf0061f96505c03e5f7b4fd735f81843c922992e57`. This validates a partial checkpoint only.

Remaining worker-owned CPU work: construct exact Native motorcycle/moped route beside verified paved shoulder and marked zone; source flagger identity, authority, orientation, signal content, visibility, governance and release; prove vehicle scope/operator control; build four distinct 30-second constructions per selected case with four cameras; run saved-source processing and Core/Lean/final decode positives/negatives; and complete independent delivery/comparison audits. Keep partial until scoped strict readiness passes.

Actor: `motorcycle_or_moped_operator`. Frozen cell: `paved_shoulder` / `travel` / `flagger`.

Witness branch: Designated zone beside a paved shoulder.

Comparison variable: `flagger_instruction_response`. Proposed physical probes: comply with authorized flagger signal; disobey the same authorized signal. These are proposed controller and scene targets, not observed behavior or legal verdicts.

Source: `inputs/training__C183370__NRS-484B-330-1__motorcycle_or_moped_operator/assignment.json`, SHA-256 `31794e23881378a6136bd10762e71caf42ad949a28ac2ca3712013242f8e8aa9`. Summary status: `recovered_requires_source_review`; exact law text and witness take precedence.

Accepted membership IDs: none. No source-hashed equivalence receipt or accepted recording contents are available locally, so no reuse is claimed.

Incomplete CPU work: Delivery package incomplete: two controlled branches are planning definitions only; no four distinct CARLA constructions, offline and compatibility proofs, saved measurement fixtures, or independent audit. Physical realization and legal outcome remain unverified.

Resume by resolving every statutory branch and exception against the law text; construct physical Native routes and controllers in the frozen cell; define measured channels and four distinct plans per selected case; run offline, compatibility, saved-only, comparison and independent audit proofs; set ready only after those proofs pass.

Update 016 status correction: missing case construction, candidate proofs and audits are actionable CPU work under START_HERE.md. This package is partial, with the frozen scope and listed resume actions preserved.
