# NRS-484B-497 at C150129

## 2026-11-23 construction and saved CPU continuation

The exact frozen clause prohibits left-side standing or parking on a laned
one-way roadway unless an erected official traffic-control device permits it.
The draft isolates requested device presence; legal one-way designation,
official authority, erection, governance, standing/parking purpose and camera
pixels remain to be sourced and reviewed. No accepted recording exists in the
frozen membership snapshot.

`native/geometry.py` authors a 120 m, single-direction driving road with a left
curb shoulder. It inserts the left-side permission signal only for the requested
present-device branch. `native/runner.py` contains the left-curb motor-vehicle
parking controller, original 600-frame/20 Hz pose and frame-map capture, four
1280x720 FFV1 source cameras, surveyed map readback and world cleanup. It has
not executed against CARLA. `build_draft.py` produced four exact primary
constructions under `draft-permission/` with source-bound config and a selectable
current-runtime `draft-permission-manifest.json`, SHA-256
`3f5cc464a622f22d3347ad3aeb7d0879bf31bd8970633f389df231dc44562a75`.
All four passed pinned `.venv-cpu/bin/python runtime.py offline` with the final
construction hashes; no simulation started. Independent `audit_draft.py` bound
the four selections, source hashes, camera invariants, and offline logs in
`draft-permission-audit.json`, SHA-256
`105493d86298519157094c4dff994e49e883212e3381fa636c7ac495331477de`.
All materialized offline bundles and logs are in `.runtime-work/c150129-cpu/`.

`parking_saved_measure.py` computes fully left-side rest candidates from saved
original footprint, velocity and four-camera frame joins. Its 0.1 m/s rest
tolerance is an engineering observation, never a legal cutoff. It requires
separate hashed one-way designation, road boundary, permission-device inventory,
and, for a present device, authority, content, erection and governance sources.
It leaves legal result null. `prove_parking_saved.py` passed three 600-frame
synthetic positives, including the retained original pose/frame-map entrypoint,
and eight missing/altered-source negatives. `parking-saved-proof.json` SHA-256
`d8cb8119730f36f5871f6f3d6fc8119986e3438c8abcded2ec5e3707420576f6`.
These are software fixtures, not original Native observations.

Pinned current `runtime.py compatibility` reached the draft manifest then
rejected missing `measurement_contract` (`KeyError`). Next CPU work: add the
selected-requirement measurement contract, source-hashed four-camera fixture
recipe, executable finalizer that consumes retained Native sources, positive and
missing-source compatibility, saved-only processing and full video decode.
Then author and prove risk-triggered fallbacks, semantic proposals and independent
delivery/comparison audits; review redundant witness/exception cases for
source-backed reuse without changing their frozen identities. Native motion,
actual pixels, official authority, legal conclusion and accepted set membership
are unverified. The four drafts are unselected and result status remains
`partial`.

Actor: `motor_vehicle_driver`. Frozen cell: `one_way_road` / `park` / `parking_restriction_device`.

Exact statutory source: NRS 484B.497. Source text and hash are in `case-plan.json`. Historical summary status: `recovered_requires_source_review`.

Selected witness: Left-side parking on a laned one-way roadway. Planned comparison variable: `one_way_left_parking_permission`. Requests: driver parks on left with governing permission device; driver parks on left without governing permission device. These are proposed targets, never measured behavior or legal verdicts.

Activation to verify: the roadway is laned and restricted to one direction; the subject stands or parks on its left-hand side; no device permits it there.

Timing to retain: judged for every instant at rest on the left-hand side.

Exceptions and numeric alternatives planned: where official traffic-control devices are erected permitting such standing or parking.

Unresolved judgment or rule composition: this line is the default prohibition and the previous one its signed counterpart; a reading must say which governs where both could apply. No judgment bound is set by this plan.

Accepted membership: 0 membership rows; exact source-hashed equivalence and reuse are unverified.

Blocker: No executable Native construction or four distinct source-preserving candidate plans have been produced; exact offline and compatibility proofs, mandatory saved measurement fixtures, and independent audits are absent. Physical feasibility and legal outcome remain unverified.

Resume: reconcile each branch against the exact law and cited provisions; establish compatible Native construction and measurement channels; produce four distinct candidate plans and exact offline, compatibility, saved-only, semantic and audit proofs; then evaluate readiness.
