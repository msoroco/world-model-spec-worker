# C230328 / NRS 484B.777(3) handoff

Status: **ready for delivery preparation**. The exact assignment strict CPU gate passed. Accepted original Native recordings and memberships: 0. The frozen road/travel_abreast/cyclist cell and cycle_or_scooter_operator actor are unchanged.

## Selected construction

- Two-rider `__controlled_1` and three-rider `__controlled_2` are selected with distinct primary and fallback1 Native candidates. The 600-frame 20 Hz runner records four canonical cameras, rider identity and pose, roadway/shoulder and exclusive-use evidence. The fallback shifts the spawn by 0.18 m if physical spawn geometry fails. Original CARLA capture remains pending.
- `measure_abreast.py` joins saved source frames, rider positions and source-bound camera frames. It retains pairwise longitudinal overlap, lateral delta and bearing without inventing a statutory numeric threshold. A convoy yields zero pairwise overlap. The source law's qualitative scope and exception remain for original review.
- Current-runtime offline passes for all four candidates. Public compatibility positives and missing rider-source negatives pass for all four. Recorded-only process-saved passes for all four with no physical or legal acceptance claim. Physical complete/incomplete/missing-evidence triads, semantic index, independent delivery positives and missing-seal negatives, and pairwise comparison audit pass. Diagnostic fixture sources remain distinct from original Native evidence.

## Exact CPU gate and bindings

- Command: `.venv-cpu/bin/python worker_check.py --assignment training__C230328__NRS-484B-777-3__cycle_or_scooter_operator --complete --require-delivery-ready`
- `strict-assignment.log`: SHA-256 `dff32bead850ddbd375c159b8fc1c42163622f5141ccd0084d21d26e2e3b02d7`; exit code 0; `static_checks_passed=true`.
- `execution-manifest.json`: SHA-256 `0f48c95950af7b0e754581b781f2f738f865344ee99af67107cdf5facaecbdcf`.
- `proposals/semantic-index.json`: SHA-256 `97a528b488c5a529839747f298779f6b9cf9e0a29aac0711ca44310ca8718425`.
- `comparison-main-audit.json`: SHA-256 `4f7032ad7d68dcf5880b4d8d3c3964b875ced5375860340de2c145d31506465e`.
- `result.json`: SHA-256 `d7bdee9eeef9c9d1ab2f31452456e182e65640c3d1612f675aaa473503265357`; readiness_kind `delivery_prepared`, `carla_executed=false`, `recordings_accepted=0`.

## First original capture

Run the `first_gpu_delivery_command` in `result.json` with a CARLA host and a sealed original job, then independently review rider identities, roadway and exclusive-use sources, frame geometry and camera originals. No diagnostic pass is a legal three-abreast verdict.
