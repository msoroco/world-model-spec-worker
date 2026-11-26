# C230286: LVMC 11.38.120(B), motorcycle or moped operator

Status: CPU delivery-prepared candidate. The selected package has 27 exact cases and 23 source-isolated comparisons. It has no accepted Native recording or legal outcome. Physical and qualitative review remain open.

## Coverage and construction

The fixed road route and separate sidewalk, covered motorcycle, trail-ride and enclosed-three-wheel coverage controls, head and tail lamp state, white/red color, calibrated 299/300/301-foot forward and 499/500/501-foot rear ranges, 499/500/501-foot forward discernibility, daytime low-light and unfavorable atmosphere, and sunset/sunrise half-hour timing are represented in `case-plan.json`. Each case has a source-gated construction and measurement contract under `cases/`. The production `runner.py` requires a hash-sealed original source packet and Native CARLA adapter; `source_packet.py`, `lamp_controls.py`, and `lamp_observations.py` reject missing, changed, or diagnostic sources. Four synchronized views run at 20 Hz for 30 seconds; calibrated lamp and atmosphere observations remain separate from video pixels and legal judgment.

## CPU proofs and queue

`execution-manifest.json` binds all 27 selected constructions to successful primary and fallback offline proofs, positive and negative compatibility, saved-only processing, three physical preparation fixtures per case, lifecycle receipts, and positive and missing-source delivery audits. The 23 controlled comparison receipts are indexed by `comparison-proofs.json`; source isolation is checked by `pair_audit.py`. The semantic proposal covers seven stages and 27 selected cases, with unresolved value-free physical and qualitative judgment calls. `queue-proposal.json` contains exact ordered prepare, execute, saved processing, source audit, and accept commands for all 27 cases plus 23 comparison audits. Shared queue integration is lead-owned.

Focused source tests: 23 passed (`cpu-source-tests.log`). Pinned preflight passed (`cpu-preflight.log`). The scoped strict delivery gate passed (`strict-assignment.log`) after all 27 selected receipts and 23 comparisons were bound to the final plan. Original CARLA frames, calibrated physical performance, selected-case acceptance, and any legal conclusion are pending local delivery and review.

Final SHA256: `case-plan.json` `98491a89e6177aeb1e8ae9c9bd141e366c88f27352c4b89294125dafc424a477`; `execution-manifest.json` `b6bed33a7dad97c18392227b9ed3c26baaa4b077d6763355d649fcc1de5d3cde`; `proposals/semantic-index.json` `082140782c822ad3510fb82b5eea6477148212cad180458ce5dc60d2e77fa2bc`; `queue-proposal.json` `8880b6127325c86670b2cae9de576cd7593e8ab99fd28a800edd616af339e35e`; `strict-assignment.log` `757df303f489e04b3c2e75a79601c1379c29e24c6ab9e40db62c6a33e144d169`. Returned-file scan: 1,080 UTF-8 files, none over 2 MiB, no trailing whitespace, blank EOF, or conflict markers.
