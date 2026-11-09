# Recording storage and end-of-set finalization

## Current review workspace layout

`work/` contains the final review collection in five folders matching the
active sets:

```text
work/<set>/<cell>--<law>/README.md
work/<set>/<cell>--<law>/<case>--<recording-id-first-12>/
  video.webm
  trace.json                  selected final lean trace
  metadata.json               compact identity, label and hash record
```

Review models used to regenerate the READMEs live under
`state/review_models/<set>/<cell>--<law>.json`. Validation receipts, earlier
traces, and previous review metadata live outside `work/` in the external
backup and operation records. There is no maintenance subtree in `work/`.

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

`refresh-workspaces` refreshes review navigation without overwriting videos,
traces or compact case metadata. Changed accepted membership requires explicit
new-output materialization.

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

This verifies evidence once and writes `membership.json`, `cases.csv`, and the
`completion.json` commit marker. It does not drive, convert, copy recordings or
create ZIP files. Identical retries return the committed receipt without
rescanning the dataset. Evidence completeness and reviewed statutory coverage
completeness are separate flags.

Only when a portable copy is needed:

```bash
python3.11 scenario_pipeline/pipeline.py package-set \
  --set demo-v1 --output runs/scenario_pipeline/state/packages/demo-v1
# Add --zip only to request an archive.
```

The package contains its own recordings, relative manifest/CSV links and
`SHA256SUMS`. Routine processing never creates packages.

## Active split sets

`pipeline.py organize-sets` now validates installed scope/selection metadata
without rebuilding membership. The five active sets are `demo-train`, `demo-test`,
`held-out`, `full-train`, and `full-test`. Their installed scopes and frozen
selections remain authoritative. Historical bootstrap and storage migrations
are archived outside the active package.

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

Finalization stays deferred. When explicitly run at the end, `finalize-set`
checks the selection's scope hash and embeds that scope in the finalized
manifest and any requested portable package. Its reviewed coverage flag stays
false until the scope and selected evidence are explicitly reconciled.

## Versioned law partitions

The active corpus split is `demo-overlap-v3`: 221 training laws, 28 held-out laws
and the unchanged 22-law demo. `sets/index.json` selects the hash-bound manifest.
Eligibility is checked by law/cell/actor; a cell may support different laws in
different sets. Training/testing witnesses for each law occupy distinct cells.

Current recording membership and metadata directly reflect this split. Historical
capture artifacts remain unchanged in saved evidence and backups. Demo review
folders link to their full-set counterparts. Superseded partition receipts are
not required for current memberships.

`pipeline.py check-law-split` verifies the installed current roster
and workspaces; it does not reactivate historical assignments. Dispatch resolves
eligibility from the active manifest and scopes. New input revisions capture the
current policy. Historical run snapshots do not control current assignments.

Training lines do not cite held-out lines under bracketed-ID and recorded-reference
checks. Held-out laws can cite training/demo laws. Held-out vocabulary introduces
`dev.school_bus_signal`, `sig.reverse_lamp`, and regulatory-sign values
`lane_use_arrow` and `turn_course_marker`.

## Shared acquisition manifest

`inputs/shared/manifest.json` describes current source acquisition capabilities.
The four non-held-out sets and evaluated recordings link to this file with relative
symlinks; set membership remains in `selection.json` and finalized `membership.json`.
Unsupported hand signals are omitted, which Core treats as absent.
A verified empty kind emits no placeholder object. Complete static inventories
clear only their verified kind masks; unresolved legal road status and incomplete
physical inventories remain explicit unknowns. Superseded traces and validation
metadata belong in the external reconstruction archive, never under `work/`.
See [trace reconstruction](traffic_spec_adapter.md#saved-evidence-reconstruction) for validation, current reports, and the external archive.

The accepted non-held-out public-road convention is recorded in
`inputs/shared/road-access.json`; each reconstruction receipt binds its hash,
original map hash and stable highway identities. Original evidence is immutable.
A trace's unchanged bytes may reuse a completed Core check only when the trace,
decoder binary and manifest hashes all match. A source-code change still runs
projection before considering this byte-level validation reuse.
Superseded delivery copies and one-time migrations belong in the external
`world-model-spec_back/` archive, never in `work/` or production modules.
