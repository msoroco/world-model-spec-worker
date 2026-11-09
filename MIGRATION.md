# Full-train runtime migration

Update 014 replaces the frozen portable runtime while retaining this batch and all 253 assignment directories. Read `updates/014-migration-receipt.json` for the prior batch hash, runtime hash and each result marker update. Work scripts, plans, configurations, comparison drafts and historical proof files were retained.

The old proofs are historical because the runtime, Core representation and validator changed. A result with `applied_update: 14` acknowledges the update; it does not certify its old proof. Re-run each exact offline construction, compatibility recipe, saved-only fixture, audit and assignment-scoped strict gate before claiming `ready`. Do not mass-replace receipts with changed hashes or mark a case ready merely to pass the gate. Use the current runtime contract only.

If a draft fails the new checker, repair that assignment and record the diagnosis in its HANDOFF.md. Keep frozen assignments and partition membership unchanged. Continue independent assignments while a particular one remains blocked.

The prior runtime fixture files removed from the current runtime remain in the parent Git commit. Their exact paths and SHA-256 values are in the migration receipt; no assignment-owned work file other than the 253 result markers changed.

## Runner handoff after the active agent stops

Wait for the current checkpoint timer to finish and confirm `worker/full-train-delivery` still points to `d237df7eddddc779c693533cd0384130867940e9`. Then, in the worker checkout:

```sh
git fetch origin worker/full-train-delivery worker/full-train-runtime-refresh
git switch worker/full-train-delivery
git merge --ff-only origin/worker/full-train-runtime-refresh
git push origin worker/full-train-delivery
scripts/run-worker.sh
```

If the active return head has advanced, do not force-push, reset, or resolve result-file conflicts by discarding work. Keep the checkpoint and have the update branch rebuilt from that head before restarting. Demo-test and held-out use separate checkouts and `scripts/run-worker.sh` on their respective branches.
