---
name: worker-preparation
description: Prepare explicitly assigned scenario packages in the portable Git worker repository, without CARLA, NERSC, SQLite or canonical acceptance. Use for exported partition batches and their CPU-only returns.
---

# Portable worker preparation

Read START_HERE.md and batch.json first. This workflow owns file routing in the
worker repository; the original six scenario skills retain their substantive
law/evidence rules. Their main-project SQLite, output-root and resource paths
are reference descriptions, not worker operations. The standalone worker's
work/<assignment-id>/ contains implementation. In the main project's
set-review-workspaces-v2 layout, work/ is accepted review output only; imported
implementation belongs in state/operations/worker_exchange/. Demo review case
symlinks intentionally share edits with full-set cases; do not restrict them.

Use inputs/<assignment-id>/assignment.json for the fixed law, cell, actor, role,
branches and objective. Read the supplied witnesses, prior guidance and declared
dependencies. Do not rebuild scope or repeat completed evidence. Missing source
material or runtime capability remains an explicit limitation.

`source_observation_terms` are legal planning prompts. The old source summary
called them atoms, but some (for example `drv.turning`) have no Core ontology
ID. Map every term in `case-plan.json.source_observation_mapping` to a named
measurement or sourced context, with evidence, channels and source_refs. Only
put IDs from the pinned `atomIds` list in `config.required_atoms`. Run the
shipped atom preflight before constructing fixtures. Conditional adapter paths
need the source packets in START_HERE.md and actual converter coverage;
unsupported paths need a tested repair or precise CPU blocker. Never remove a
law requirement to make the converter pass.

The lead may delegate at most batch.max_workers independent assignment owners.
Each subagent writes only work/<assignment-id>/; only the lead integrates shared
changes and commits/pushes the return branch. Frozen runtime helpers cannot be
edited. Portable repairs go through the tested, source-hashed shared overlay
described by `overlay.py`. A shared demo/full assignment is one task even if multiple partitions
reference it. Process remaining partitions in waves; do not wait for conversation
when independent work is available.

Implement configuration-driven construction/controllers, capture checks and
saved-only conversion/rendering/auditing as required by the assignment. Keep
all generated files and fixtures small and textual. CPU tests must not connect
to CARLA. Run runtime checks lazily, not at module import. Small fake fixtures
can test schemas and joins, never establish physical capability or acceptance.

Use result.json and HANDOFF.md under the assignment directory. Report commands,
exit codes and hashed logs, implementation assumptions and remaining GPU checks.
Prepared means CPU-tested and ready for local runtime verification. It does not
mean physically verified, accepted, compliant or statutorily complete. For
missing dependencies, commit a partial/blocked result and continue other work.

Never run NERSC tools, use the main campaign database, drive a simulation,
register a recording, relabel research, or modify set membership. Run
python3.11 worker_check.py --complete --require-capability-ready before returning the batch. Follow the
exact result format in START_HERE.md.

## Shared runtime

Read START_HERE.md and use the version/hash bound in batch.runtime. Reuse supplied
capture, conversion, rendering and validation; never recreate those components.
Every executable package, including partial packages, needs a validated
execution-manifest.json listing every expanded nonbaseline case and an exact
construction SHA. Capability packages need executable measurement/finalization
code, not just a note that a GPU is needed. Distinguish readiness_kind capability
from delivery_prepared; neither means physical acceptance. Run the shared actual
fixture selftest and every case offline check. Push the configured return branch
when finished. Operator launch is manual.

## Output compatibility

Write canonical frame identities during capture
with native_output.FrameMap and finalize measured results with write_result. Do
not translate or rewrite faulty original evidence after capture. Use world_restore
snapshot/restore with guaranteed cleanup and readback, keeping resource ownership
local. Reuse environmental acquisition methods; a named channel is not a source.
Every exact case needs acquisition mappings and a source-bound compatibility
receipt from its actual bundled analysis, existing validator, converter and video
processing. The generic runtime selftest alone cannot qualify a new package.
The v5 batch also requires a selected-requirement measurement contract and a
case-specific positive/negative fixture recipe. Each selected requirement has
a concrete saved finalizer output and exact source hashes. Keep generated
fixture trees and rendered media in ignored `.runtime-work/`, committing only
small source inputs, logs and receipts. The first GPU command supplies a local
CARLA Python via `--python "$CARLA_PYTHON"`.
Fixtures establish software compatibility only; unknown physical outcomes remain
unconfirmed. Do not drop mandatory observations or fabricate physical success to
pass tests. Validate one exact case end to end before expanding all partitions.
