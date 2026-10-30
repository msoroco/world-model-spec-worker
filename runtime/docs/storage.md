# Recording storage and end-of-set finalization

## Current review workspace layout

The `set-review-workspaces-v2` migration replaces the old implementation-oriented
`work/` layout with five review folders matching the active sets:

```text
work/<set>/<cell>--<law>/README.md
work/<set>/<cell>--<law>/review.json
work/<set>/<cell>--<law>/<case>--<recording-id-first-12>/
  video.webm
  trace.json
  metadata.json
  receipts/
```

`full-train`, `full-test`, and `held-out` contain independent regular review
copies. Recording directories in `demo-train` and `demo-test` are relative
directory symlinks to their corresponding full sets. Edits, file replacement,
additions, and deletions are shared between demo and full-set paths. There are no
editing or immutability restrictions on these review files. Set-specific READMEs
remain separate because demo membership is a subset of full-set membership.
Canonical recordings and raw evidence outside `work/` are unchanged.

Only assignments with accepted recordings appear in this tree. Their remaining
requirements stay explicit; copying a review output does not finalize a set or
establish full legal coverage. Existing selection and scope files remain the
membership authority. New processing administration and intermediate artifacts
use `state/operations/<run>/` rather than recreating campaign folders in `work/`.

Worker exchange imports follow this same separation: prepared implementation
goes to `state/operations/worker_exchange/<batch>/<package>/<assignment>/`,
while frozen exchange inputs/receipts stay under `inputs/worker_exchange/`.
The import also retains a verified `local-checkout/` beside the assignment
directories. It contains the portable runtime, inputs and ordered GPU queue in
their original relative layout, so local execution needs no worker Git checkout.
Its `.runtime-work/` scratch remains under `state/operations/`; the import
receipt records the exact local path and source-tree hash.
The standalone worker Git repository's `work/<assignment>/` is implementation,
not a mirror of this review tree. Import does not materialize review outputs,
modify demo symlinks or restrict edits to review files.

The complete previous work tree is retained under the external backup root.
`state/lean-work-migration.json` and `work/index.json` identify its exact location
and the backup receipt. Archived campaign paths remain available as historical
provenance. `refresh-workspaces` refreshes review navigation without overwriting
edited review payloads; changed accepted membership requires explicit new-output
materialization. It does not replay the old workspace bootstrap.

Migration CLI (dry run by default):

```bash
python3.11 scenario_pipeline/lean_work.py --root OUTPUT_ROOT --backup BACKUP_ROOT
# Add --apply to stage, verify, archive and install, or resume an interrupted cutover.
```

The older implementation-layout descriptions below document historical storage
and recovery behavior. For an index marked `set-review-workspaces-v2`, this
section supersedes their `work/` routing and navigation conventions.

Every persistent artifact lives under `SCENARIO_PIPELINE_OUTPUT_ROOT` (default:
`runs/scenario_pipeline`). There is one supported layout:

```
state/                         campaign databases and migration journal
inputs/                        frozen inputs and implementation bundles
recordings/<recording-id>/      one folder per distinct recording
  video.webm                   accepted full-trace primary video
  trace.json                   accepted Lean/Core JSON trace
  metadata.json                identity, status, hashes, acceptance, timings
  evidence/                    native observations, source footage, diagnostics
sets/<set-id>/                 selection and finalized metadata
work/<category>/<cell>/<law>/  editable implementation, plans and comparison audits
```

Execution writes directly into `recordings/<recording-id>/evidence`. Case
acceptance registers the full video/trace pair in that same recording folder.
Native evidence and failed attempts are retained. Acceptance does not copy a
campaign, generate an archive, or consolidate earlier cells.

## Define and finalize a set

Write `sets/<set-id>/selection.json` before dispatching selected comparisons.
Freeze membership before execution; extend selection through a new version.
For example:

```json
{
  "frozen": true,
  "reviewed_coverage_complete": false,
  "members": [{
    "campaign": "demo",
    "law_id": "NRS-484B-127-3",
    "cell_id": "C228508",
    "actor": "motor_vehicle_driver",
    "case_id": "selected-case",
    "split": "training",
    "status": "accepted",
    "recording_id": "recording-metadata-id"
  }]
}
```

Recording IDs come from `metadata.json` or the case's `recording_id` in the
run-local delivery index. Splits must be `training`, `testing`, or `heldout`.
Update dispositions as work completes without changing selected identities.
A nonaccepted terminal member needs `status: failed|unsupported|unselected` and
an explicit `reason`. Pending/running selections block finalization. Explicit
reuse carries an immutable `reuse_receipt` and preserves the source identity.

```bash
python3.11 scenario_pipeline/pipeline.py finalize-set --set demo-v1
```

This verifies evidence once and writes `manifest.json`, `cases.csv`, and the
`completion.json` commit marker. It does not drive, convert, copy recordings or
create ZIP files. Identical retries return the committed receipt without
rescanning the dataset. Evidence completeness and reviewed statutory coverage
completeness are separate flags.

Only when a portable copy is needed:

```bash
python3.11 scenario_pipeline/pipeline.py package-set \
  --set demo-v1 --output runs/scenario_pipeline/work/packages/demo-v1
# Add --zip only to request an archive.
```

The package contains its own recordings, relative manifest/CSV links and
`SHA256SUMS`. Routine processing never creates packages.

## One-time migration

```bash
PYTHONPATH=scenario_pipeline python3.11 scenario_pipeline/migrate_storage.py \
  --root /absolute/path/to/runs/scenario_pipeline
PYTHONPATH=scenario_pipeline python3.11 scenario_pipeline/compact_storage.py \
  --root /absolute/path/to/runs/scenario_pipeline
```

Migration requires no live leases and holds the exclusive runtime-edit lock.
The resumable journal is `state/storage-migration.sqlite`; the completed receipt
is `state/storage-migration.json`. Sealed records retain their exact bytes.
Former path strings are provenance. The journal identifies relocated artifacts
and their content hashes; operational attempt locators and delivery indexes use
canonical locations.

Unknown historical splits remain `unassigned` and block set finalization until
an explicit assignment is supplied. Failure states and unsupported coverage stay
visible. Duplicate export trees are removed only after every unique file has a
verified retained destination.

`pipeline.py status --run RUN` reads SQL counts without writing reports.
`pipeline.py report --run RUN` explicitly materializes an optional campaign
progress report. Routine selection, semantic stages, and simulation do not
automatically rebuild it.

## Active split sets

Run `python3.11 scenario_pipeline/pipeline.py organize-sets` from the project
root to organize the existing evidence and precomputed coverage into:

| Set | Planned coverage | Existing recording membership |
| --- | --- | --- |
| `demo-train` | 22 demo laws within training cells | Training demo pairs and compatible production pairs for demo laws |
| `demo-test` | 22 demo laws within testing cells | Existing testing demo pairs |
| `held-out` | 28 held-out laws across 28 precomputed cells | Historical held-out pairs plus held-out demo pairs |
| `full-train` | 221 laws across 149 precomputed training cells | All compatible training pairs, including `demo-train` |
| `full-test` | 221 laws across 142 precomputed testing cells | All compatible testing pairs, including `demo-test` |

`sets/index.json` identifies the five active sets and the preserved historical
sets. `selection.json` references recordings; `scope.json` references the frozen
precomputed cells and reviewed law/actor/branch witnesses, with source hashes.
Full sets contain their demo memberships using the same recording IDs, without
copying payloads. Names use `train`/`test`; member split values remain
`training`/`testing`/`heldout`.

The sources are the focused precomputed partition and continuation v32's updated
22-law scope. The exhaustive planner's blocked selection is not used. Scope
lists retain every precomputed full/held-out cell, including cells without a
reviewed coverage assignment. Reviewed assignments link candidate recordings;
they remain pending review until reconciled against their exact requirements.
Old accepted status alone does not establish current branch completeness.
Historical recordings targeting other laws are listed separately from planned
law coverage.

The user explicitly retained 25 historical held-out recordings from
training-owned cells. These appear as `historical_split_exceptions` in the
held-out scope and membership. **The active sets therefore have historical cell
overlap.** Those recordings remain held-out and are excluded from training
reuse. New work uses the precomputed cell ownership. Previously unassigned
production membership receives a sourced split assignment from that ownership;
its original recording metadata stays unchanged.

The organizer checks primary-file existence and recording identities, references
the completed preservation audit, and does not rescan raw footage. It leaves the
six old sets unchanged. Repeating it with identical inputs writes no dataset
metadata. Before changed active metadata is replaced, its exact bytes are saved
under `inputs/bundles/set-organization/<snapshot-id>/`; finalized sets cannot be
reorganized. The receipt is `state/set-organization.json`.

This command rebuilds imported membership and planned scope from its documented
sources; it is a migration/indexing command, not an automatic processing step.
If active metadata has been edited since organization, the preceding version is
snapshotted before rebuilding. Keep subsequent case selections and reviewed
coverage reconciliation in a new frozen selection version rather than routinely
rebuilding from historical imports.

Finalization stays deferred. When explicitly run at the end, `finalize-set`
checks the selection's scope hash and embeds that scope in the finalized
manifest and any requested portable package. Its reviewed coverage flag stays
false until the scope and selected evidence are explicitly reconciled.

## Active implementation workspaces

Start at `work/README.md` or `work/index.json`. The supported editable layout is:

```text
work/demo/<cell>/<law>/       demo implementation, shared by its dataset sets
work/held-out/<cell>/<law>/   held-out implementation and retained exceptions
work/train/<cell>/<law>/      other training implementation
work/test/<cell>/<law>/       other testing implementation
```

Use full law IDs. Actors retain separate identities in the workspace index and
in actor-specific artifacts. Source-named children preserve distinct historical
implementations; the workspace README links these, coverage dispositions, exact
recording IDs, and the set scopes/selections. A planned workspace without source
implementation remains visibly pending. Dataset membership and progress counts
are derived from the existing sets, not maintained as another status database.

Cell-wide semantic definitions live under `<cell>/_shared/semantic/<campaign>/<actor>`.
Campaign administration lives under `<category>/_campaigns/<campaign>`. Use
`workspaces.campaign_path`, `semantic_directory`, and `artifact_directory` for
operational output routing. Saved-only processing uses those same paths. Native
attempts still write directly to `recordings/`; frozen consumed inputs still
belong in `inputs/`; SQLite remains authoritative for job/attempt state in
`state/`. The workspace index is navigation and output routing, not acceptance
or a law evaluator.

To migrate existing implementation by verified independent copies:

```bash
python3.11 scenario_pipeline/pipeline.py organize-work --dry-run
python3.11 scenario_pipeline/pipeline.py organize-work --apply
```

The command requires idle campaign jobs/leases and exclusive runtime/task locks.
It copies implementation, small configuration/report files and Lean sources;
SDKs, build caches, native footage and raw frame streams stay in their existing
stores. These retained frozen dependencies are not reproduced as editable work.
Historical JSON evidence and receipts retain their bytes. Path literals in copied
Python/shell implementation are adapted to relocated work; those copies require
new frozen implementation/runtime provenance and dependency checks before use.
The command does not replay or repair native attempts.

Original campaign directories and input bundles remain unchanged for recovery.
Do not create new implementation there. Mutable run output locations and copied
delivery indices point to the new work structure; jobs, immutable artifacts,
recording payloads, selected identities and scope hashes are preserved.
`sets/index.json` points to the one shared workspace index. Full sets reference
their demo workspace instead of creating competing implementations.

The copy journal is `state/workspace-migration.sqlite`; the receipt is
`state/workspace-migration.json`. SQLite backups precede output-locator changes.
Source changes during copying block cutover; independent destination edits are
never overwritten. An unchanged repeat verifies the journal and returns its
receipt. This is a migration command, not a per-case processing step. Do not
rerun it after editing the new workspaces; retain subsequent implementation
versions and update navigation deliberately.

After accepting more evidence or updating coverage dispositions, run
`pipeline.py refresh-workspaces` to refresh the derived index and readable
navigation. This reads set metadata, preserves implementation edits, and does
not copy evidence, consolidate datasets, or rerun migration. Workspace READMEs
are generated navigation; put authored progress and resume instructions in
`HANDOFF.md` or implementation-specific files instead.

Required campaign decoder executables are retained individually under
`inputs/adapters/validators/<sha256>/adapterCheck` and registered in the shared
workspace index. `workspaces.validator_path` resolves that frozen input. The
rest of an SDK/build cache is not copied. Composed Python paths are adapted by
static AST inspection without executing old runners; references to frozen input
context stay in `inputs/`, and omitted frozen dependencies retain their explicit
locations. Historical sources not parseable by the scheduler's Python version
are retained as history and listed in the path-repair receipt.

## Versioned law partitions

The active corpus split is `demo-overlap-v3`: 221 training laws, 28 held-out laws
and the unchanged 22-law demo. `sets/index.json` selects the hash-bound manifest.
Eligibility is checked by law/cell/actor; a cell may support different laws in
different sets. Training/testing witnesses for each law occupy distinct cells.

Current recording membership and metadata directly reflect this split. Historical
capture artifacts remain unchanged in saved evidence and backups. Demo review
folders link to their full-set counterparts. Superseded partition receipts are
not required for current memberships.

`pipeline.py migrate-law-split --dry-run` verifies the installed current roster
and workspaces; it does not reactivate historical assignments. Dispatch resolves
eligibility from the active manifest and scopes. New input revisions capture the
current policy. Historical run snapshots do not control current assignments.

Training lines do not cite held-out lines under bracketed-ID and recorded-reference
checks. Held-out laws can cite training/demo laws. Held-out vocabulary introduces
`dev.school_bus_signal`, `sig.reverse_lamp`, and regulatory-sign values
`lane_use_arrow` and `turn_course_marker`.
