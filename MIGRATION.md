# Full-train runtime migration

Update 014 replaces the frozen portable runtime while retaining this batch and all 253 assignment directories. Read `updates/014-migration-receipt.json` for the prior batch hash, runtime hash and each result marker update. Work scripts, plans, configurations, comparison drafts and historical proof files were retained.

The old proofs are historical because the runtime, Core representation and validator changed. A result with `applied_update: 14` acknowledges the update; it does not certify its old proof. Re-run each exact offline construction, compatibility recipe, saved-only fixture, audit and assignment-scoped strict gate before claiming `ready`. Do not mass-replace receipts with changed hashes or mark a case ready merely to pass the gate. Use the current runtime contract only.

If a draft fails the new checker, repair that assignment and record the diagnosis in its HANDOFF.md. Keep frozen assignments and partition membership unchanged. Continue independent assignments while a particular one remains blocked.

The prior runtime fixture files removed from the current runtime remain in the parent Git commit. Their exact paths and SHA-256 values are in the migration receipt; no assignment-owned work file other than the 253 result markers changed.

## Current launch

The refreshed runtime has been promoted to `worker/full-train-delivery`. Start from a fresh checkout using the command in `README.md`. The historical migration and update receipts above remain provenance; they do not authorize old proofs as current evidence.
