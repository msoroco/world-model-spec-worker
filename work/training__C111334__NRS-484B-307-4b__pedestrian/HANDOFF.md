# NRS-484B-307-4b at C111334

Actor: `pedestrian`. Frozen cell: `intersection` / `travel` / `turn_arrow`.

Exact statutory source: NRS 484B.307(4)(b). The law text is retained in `case-plan.json`; extracted summary status is `recovered_requires_source_review`. Witness branches: Travel route containing highway entry.

Controlled planning variable: `pedestrian_highway_entry_before_permission`. Proposed requests: pedestrian waits for permitting device; pedestrian enters highway facing green turn arrow alone without other permission. These are scene/controller targets, not observed conduct or legal verdicts.

Statutory alternatives and exceptions still to cover or disposition: other-device permission under 484B.283.

Accepted membership: 0 distinct recording IDs. Their contents and exact source-hashed equivalence are unavailable in this checkout, so reuse is not claimed.

Blocker: No executable Native construction, four distinct source-preserving candidates, offline/compatibility proofs, measured-result contract, positive/negative saved fixtures, independent audit, or verified source-hashed reuse receipt has been produced. Physical realization and legal outcome are unverified.

Resume: reconcile every branch against exact text and physical cell; construct Native routes and controllers, mandatory measurement mapping, four distinct plans per selected case, and execute pinned-runtime offline, compatibility, saved-only and independent audit proofs. Mark `ready` only after all CPU proofs pass.

## 2026-11-23 permission and source-measurement checkpoint

The exact text requires the green turn arrow alone to face the pedestrian and bars highway entry until another device permits proceeding. The case plan now includes a third planned, unselected `permission_before_entry` case. Its controlled comparison holds the arrow, pedestrian route, highway boundary and entry trajectory fixed against `probe_2` while changing the other device's permission timing. This closes the missing planned alternative; it does not prove a physical signal or lawful crossing.

`native/measure_entry.py` measures a 600-frame, 20 Hz source packet with a hashed map, device identity/facing and frame stream. In synthetic diagnostics, waiting never enters; the unpermitted entry first occupies the highway at frame 134 without another-device permission; the same entry path with permission at frame 100 is classified as entry after permission. Four negatives reject altered source bytes, a missing frame, a nonfacing head and an arrow state that is not green turn arrow alone. The report `native/entry-source-proof.json` has SHA-256 `584d3d92aba493026b55df3eaed7afb402b244e916696aa2d20a44d6227f5ad1`, the measurement code SHA-256 `e60bd985fb877b2f3a689a1f75bd04cbb0d06391ecd2a24e1e644d080eca2397`, and the proof script SHA-256 `abfb319b94430290b9222c3a3beec0dc0b9bd01f04eb162cad6c06e44a8db966`. Pinned preflight and assignment-scoped `worker_check.py --complete` exit 0.

The package remains partial. The three cases are planned only; no Native controller/construction, four-camera exact candidate proofs, current saved processing, independent acceptance/comparison audit, semantic or queue package has been produced. The source packet is synthetic and cannot establish original head pixels, pedestrian motion, device permission under NRS 484B.283 or a legal verdict. Next CPU work is a source-retaining Native controller and exact candidate construction for all three cases, then current-runtime offline, positive/negative saved processing and independent audits.
