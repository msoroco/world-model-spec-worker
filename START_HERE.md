# Fresh demo-test preparation trial

The operator starts this agent manually. Read `batch.json`, the four JSON
partitions, `skills/worker-preparation/SKILL.md`, the exact frozen assignment
inputs, and the examples. Work only on those 22 assignments. Do not copy
packages, fixtures, labels or readiness claims from earlier trials.

Use up to four assignment owners, one per partition at a time. The lead alone
integrates shared changes, runs acceptance, commits and pushes the configured
`batch.return_branch`. Do not force-push. Do not run CARLA, NERSC tools, or the
main campaign database.

For each assignment, derive exact cases and comparisons from the law, cell,
witness and prior evidence. Build executable construction, controls, cameras,
capture channels and CPU checks. `source_observation_terms` are legal planning
terms. Map **every** term in `case-plan.json.source_observation_mapping` to
measured evidence. Each map value has `evidence`, `channels` and `source_refs`;
at least one of the latter two lists must be nonempty. A source term is never
automatically a Core atom.

Before building compatibility fixtures, run the pinned atom gate on every
case's `config.required_atoms`:

```sh
python3 -m unittest tests.test_atom_preflight
python3 worker_check.py
```

Only the pinned Core ontology IDs with a supported adapter path may appear in
`required_atoms`. For example, `drv.turning` is a legal evidence question:
capture route, pose, heading and actual turn history instead. The ontology
contains `st.one_way_roadway`, but the pinned adapter cannot produce it; keep
the legal requirement and report that capability gap until implemented. Do
not delete a requirement to make a test pass.

For a `ready` package, run every exact case's offline runner check, assignment
tests, actual bundled analysis, native validator, Core converter and video
checks using the shipped runtime. Bind logs and compatibility receipts to the
specific case and implementation. Fake fixtures prove software compatibility
only. Record unverified CARLA motion, duration and pixel visibility separately.

Finish with `python3 worker_check.py --complete --require-ready`. If an
assignment cannot meet readiness, submit `partial` with its precise capability
gap; do not call it ready. Commit and push the return branch, then report its
commit and counts. No simulation or physical acceptance is claimed here.
