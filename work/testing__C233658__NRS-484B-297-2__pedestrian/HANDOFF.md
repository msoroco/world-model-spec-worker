# C233658: NRS 484B.297(2) pedestrian delivery

Status: **delivery prepared**. The scoped strict worker check passes. Physical and legal acceptance require original CARLA capture, reviewed site evidence, and independent pixel and trajectory review.

## Exact scope

The six cases in `case-plan.json` cover east and west approaching traffic, a left versus right highway side for each approach, and facing versus walking with traffic on the left side for each approach. Five controlled comparisons isolate those differences. The assignment-local `proposals/branch-coverage-proposal.json` has one runnable branch per comparison; its union covers the six cases. The pinned `worker_exchange.branch_coverage.validate` passed in an isolated exact-law fixture.

The frozen evidence inventory has no accepted recordings. NRS 484B.297(2) applies to walking along a public highway without a sidewalk, subject to subsection 6. The original reviewed site packet must establish public highway status, access, boundaries, sidewalk absence, and subsection 6 nonapplicability. The packet and OpenDRIVE map hashes are checked before Native action. The exact cell fixes a straight pedestrian, `road_without_sidewalk`, and another vehicle. No legal numeric threshold is invented.

## Construction and proofs

`execution-manifest.json` binds six primary and six fallback constructions. `runner.py` invokes `native_entry.py` after the site gate. Native construction uses source-reviewed pedestrian and vehicle routes, records 20 Hz original transforms and frame mapping, captures four synchronized FFV1 cameras, retains a pixel review packet, seals the capture, and restores world state. Fallback1 changes the bounded walker speed from 1.0 to 0.8 m/s if synchronized body visibility fails. The original physical route and pixel outcome remain untested until GPU execution.

Current source bytes pass 12 offline checks, 12 package compatibility checks with missing-source negatives, six saved-only processing checks, six synthetic physical and ownership lifecycle fixture checks, six independent delivery audits with negatives, and five comparison audits with negatives. Proof inventories and hashes are in `cpu-*-proofs.json`; each manifest entry binds the case receipts. The independent audits require original source hashes, frame/time joins, full four-camera decode, actual pixel review for live attempts, physical walking progress, and separate original sources for comparisons. Diagnostic fixtures make no physical or legal acceptance claim.

Run the scoped gate with:

```sh
PYTHONDONTWRITEBYTECODE=1 SCENARIO_PIPELINE_OUTPUT_ROOT="$PWD/.runtime-work/pedestrian-output" .venv-cpu/bin/python worker_check.py --assignment testing__C233658__NRS-484B-297-2__pedestrian --complete --require-delivery-ready
```

`gpu-queue-proposal.json` supplies exact prepare, execute, owner release, saved-only processing, source audit, acceptance, fallback, and five comparison commands. Set `C233658_ORIGINAL_SITE_PACKET` to the reviewed source-hashed site packet. The operator supplies the actual saved attempt path after owner release. The queue commands passed `bash -n`.
