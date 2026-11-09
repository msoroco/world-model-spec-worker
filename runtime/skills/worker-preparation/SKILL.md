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
review workspace layout, work/ is accepted review output only; imported
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
edited. Propose shared-helper repairs inside the owning assignment for local review
and integration; readiness proofs must pass the pinned exported runtime. A shared demo/full assignment is one task even if multiple partitions
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
python3.11 worker_check.py --complete --require-delivery-ready before returning this batch. Follow the
exact result format in START_HERE.md.

## Shared runtime

Read START_HERE.md and use the source-hashed runtime bound in batch.runtime. Reuse supplied
capture, conversion, rendering and validation; never recreate those components.
Every ready package needs a validated execution-manifest.json listing every
expanded nonbaseline case and an exact construction SHA. Partial packages may
checkpoint construction without completed proofs; list missing proofs explicitly. Every selected case needs executable measurement/finalization
code, not just a note that a GPU is needed. Use readiness_kind delivery_prepared
and kind delivery for selected cases; neither means physical acceptance. Run the exact offline construction check and the case-specific positive/negative
compatibility check for every selected case and candidate. Reuse an existing
proof only when its construction, runtime, diagnostic sources, measurement
contract, and checker bindings still match. The shared runtime selftest is
optional installation diagnostics and does not establish delivery readiness. Push the configured return branch
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
Every selected case requires a selected-requirement measurement contract and a
source-hashed diagnostic recipe. Each selected requirement names a concrete saved
finalizer output and its source files. The compatibility check must process the
positive inputs and reject a missing required source. Shared diagnostic assets
must be explicitly declared and appropriate to the selected case. Keep generated
fixture trees and rendered media in ignored `.runtime-work/`, committing only
small source inputs, logs and receipts. The first GPU command supplies a local
CARLA Python via `--python "$CARLA_PYTHON"`.
Use the current law split only and follow the
four-camera `worker_exchange.capture.PROFILE`. Commit a case-specific camera
and duration plan, synchronized source capture, and a composed primary video.
The shared ready gate checks the declared plan and configuration; local Native
preflight and the first CARLA run check execution and physical visibility.
Fixtures establish software compatibility only; unknown physical outcomes remain
unconfirmed. Do not drop mandatory observations or fabricate physical success to
pass tests. Validate one exact case end to end before expanding all partitions.

## Full statutory coverage

Read FULL_BRANCH_CONTRACT.md and DELIVERY_CONTRACT.md. Same-cell branch reuse is the default. Account for every source topic and independently identify all alternatives and exceptions. Return executable controlled comparisons and saved-only automation for all runnable branches. A single capability case and empty comparisons fail the full coverage gate.

Supply every canonical semantic
stage proposal, exact delivery designation, and CPU-tested independent audit.
The remote worker writes files only; local SQLite job adoption and NERSC GPU
ownership remain entirely local. Do not modify frozen inputs in place.

## Risk-based candidate constructions

Assess every exact case for a specific Native motion or camera risk. Keep one primary construction and add at most two named fallbacks only for a concrete physical risk. A fallback is an alternate implementation of the same planned case, not another recording or cell. Record a measurable failure trigger and exact engineering changes. Keep the case, law, actor, required observations, cameras, duration and comparison variable fixed. Run exact offline and positive/negative compatibility checks for each fallback using `runtime.py offline --candidate fallback1` and `runtime.py compatibility --candidate fallback1`. The saved processor verifies the selected candidate in the attempt. Never choose by desired legal outcome. The lead independently reviews risk assessments and comparison isolation before the strict gate.

Use `runtime.py preflight` before assignment work and the supplied deterministic
textual fixture example to learn the source formats. Adapt case-specific inputs;
never claim its synthetic media as physical evidence. Use `worker_check.py
--assignment ID --complete` for a checkpoint, then add `--require-delivery-ready`
for a finished assignment. Preserve partial progress and continue independent
assignments. Review evidence.json and document exact gaps or source-backed reuse
before adding captures. The final batch gate remains mandatory.

## Operational sight distance

`st.sight_distance` supports the declared incoming-lane virtual-observer proxy.
Put it in required_atoms when needed: shared PipelineCapture activates the existing
rays automatically. No measured real driver-eye pose is required. The default is
1.4 m above lane waypoints, testing the measured ego bounding-box centre and eight
corners. Capture all inventoried approaches, including opposing lanes; incomplete
coverage or stale body samples leaves the value unknown. Preserve brackets and
censoring: clear through 230 m is a lower bound, not an occluder at 230 m. Use the
shared capture/projection, and test source-shaped packets with this declared
convention before the GPU run. This does not establish actual driver perception,
rel.visible, st.sight_along_way or legal compliance.
