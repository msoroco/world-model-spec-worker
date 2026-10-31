# Full-train delivery contract

Use `batch.json` and `inputs/<assignment-id>/assignment.json` as fixed inputs.
The batch contains 253 distinct training law/cell/actor assignments across 221
laws. Account for every topic in `inputs/coverage/branch-sources.json` in
`work/_shared/branch-coverage.json`. Same-cell constructions are the default.
Do not silently move a branch to another cell or use a held-out/test cell.

The assignment's `selection_targets` names the only eligible set selections.
Many target only `full-train`; demo-overlap assignments target both
`demo-train` and `full-train` with the same recording ID. Existing accepted
recordings are context and possible explicitly proven reuses; do not plan a
replay merely to duplicate them. Membership-only rows do not establish
current statutory coverage.

Every runnable source branch needs controlled delivery cases and comparisons.
Keep legal requirements, measured Native evidence and Core atoms separate.
Only pinned ontology IDs may enter `config.required_atoms`. Neutral baselines
remain in proposals but are not selected recordings.

Each selected manifest entry has `kind: "delivery"`, an independent saved
audit, mandatory measurement contract, positive/negative saved fixtures,
and four construction plans: one `primary` and `fallback1` through
`fallback3`. Each fallback needs a distinct construction SHA, measurable
trigger, changed engineering knobs, exact offline proof and positive/negative
compatibility proof. Preserve law, cell, actor, case, source packets, rate,
duration, cameras, recording description and comparison variable across
its candidates. Do not vary legal outcomes to make fixtures pass.

Use the shared `runtime.py` for materialization, offline checks, compatibility,
saved processing and rendering. Do not duplicate its capture or converter.
Tests and fixtures are CPU diagnostics, not selected delivery recordings.

Write an ordered `work/_shared/gpu-queue.json` with exact prepare, execute,
owner release, saved processing, acceptance and comparison-audit commands.
Every case row includes commands for all three fallbacks. Use variables for
local DB, Native Python, host, port, job and attempt IDs. Never embed NERSC
paths or presume a GPU host.

Run the full runtime selftest, every exact primary/fallback offline and
compatibility recipe, saved-audit positive/negative fixtures, semantic stage
validation, comparison audits, entrypoint tests and strict gate. Set each
`result.json` to `ready`/`delivery_prepared` after its CPU proofs pass, then
run the strict gate. The gate validates that claim. No CARLA run, recording
acceptance or legal outcome is claimed by the worker.

## Best-effort publication

Continue independent assignments when one fails. Run the strict gate at the end even if it reports incomplete packages. Commit and attempt to push all completed work, partial results, precise blockers, hashed gate logs and resume instructions regardless of gate outcome. A failed gate remains a failed gate; do not relabel a partial package ready. If remote access or automatic approval rejects the push, preserve the local commit and report that rejection without bypassing it.

## Progress publication

The lead checkpoints coherent assignment bundles after every eight completed packages or at least every 30 minutes with changed files. Use `scripts/checkpoint.sh`, which stages only `work/`. Subagents never commit or push. Record a rejected push and continue independent work; the final best-effort push remains required.
