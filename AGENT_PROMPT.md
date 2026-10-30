# Agent task: full-train GPU-ready delivery preparation

You are the lead worker agent in this repository. Complete the frozen
`full-train-delivery` batch from scratch. Use **eight subagents**, assigning
one of `partitions/full-train-01.json` through `full-train-08.json` to each.
If your platform cannot run eight at once, process the eight owners in waves;
keep assignment ownership disjoint and finish all eight. The lead alone edits
shared files and commits/pushes the return branch. Do not ask for routine
clarifications; record precise blockers and continue independent work.

Read `START_HERE.md`, `DELIVERY_CONTRACT.md`, `batch.json`, every partition,
the seven `skills/*/SKILL.md` files, and the runtime's stage and ontology
contracts. Use `examples/` as adaptation references. `inputs/<assignment-id>/`
contains the exact law, catalog cell, actor, witnesses, prior guidance,
accepted membership snapshot and selection targets. Some summaries conflict
across historical sources or are explicitly unreviewed; reconcile them
against exact law text and witness context before choosing observables.
Never invent a historically accepted requirement ID or treat a model metric
as a legal rule.

Your output must be a **deployable delivery return**, not synthetic test cases
or one research capability example per assignment. Plan all supported
statutory branches, alternatives and exceptions for all 221 laws, using the
same frozen cell for compatible branches. For each runnable branch, write
controlled comparison cases, semantic stage proposals, Native construction,
controllers, cameras, capture channels, measured-results finalization, Core
mapping, saved-only processing and independent acceptance audits. Identify
unsupported physical branches explicitly. Do not replan an already accepted
original when a source-hashed equivalence receipt proves reuse.

For **every selected delivery case**, produce exactly four genuinely distinct
CARLA construction plans: `primary`, `fallback1`, `fallback2`, `fallback3`.
Each fallback changes documented engineering knobs to address a measurable
risk such as route connectivity, braking completion or camera framing. It
must retain case identity, legal context and comparison variable. Prove each
construction's offline checks and positive/negative compatibility recipe.
Never claim a CPU fixture proves physical success.

This branch is deliberately lean: one `runtime/pipeline`, no prior trial
returns, no compatibility shims and no generated media in Git. Use only the
shipped runtime and pinned Core ontology. Keep generated fixture media under
ignored `.runtime-work/`; commit small code, plans, logs and hashed receipts.
Do not access NERSC, CARLA servers, campaign SQLite, canonical recordings,
GitHub issues or main-project set files. Do not alter frozen inputs or
`batch.json`. The local operator chooses an exact prepared candidate and
independently accepts evidence later.

The lead reviews every assignment and shared law matrix. Validate all
nonbaseline exact cases, all four candidate plans per case, every comparison,
the ordered delivery queue and synthetic local integration proof. Set
`status: "ready"` and `readiness_kind: "delivery_prepared"` only after
worker-owned CPU proofs pass. Then run:

```
python3.11 worker_check.py --complete --require-delivery-ready
```

Repair failures and rerun affected proofs. When the strict gate passes,
commit and push `worker/full-train-delivery`. Report the commit; assignment,
law, branch, case, comparison, reuse and candidate counts; gate log SHA-256;
exact remaining worker-owned blockers; and unverified physical assumptions.
Never claim CARLA execution or accepted recordings.
