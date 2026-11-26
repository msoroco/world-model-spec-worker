# C227824 pedestrian signal entry handoff

Status: **partial, source gated**. The four selected diagnostic cases are CPU prepared. No original physical capture or legal permission judgment is claimed. The exact strict gate exits 1 with `Preparation acceptance failed: partial/missing packages remain` because this package remains partial.

## Exact selected scope

- `testing__C227824__NRS-484B-307-9c__pedestrian__enter_no_other_device`
- `testing__C227824__NRS-484B-307-9c__pedestrian__wait_no_other_device`
- `testing__C227824__NRS-484B-307-9c__pedestrian__enter_walk_display`
- `testing__C227824__NRS-484B-307-9c__pedestrian__wait_walk_display`

Controlled comparisons: `entry_vs_wait_none`, `other_device_display_entry`, and `entry_vs_wait_walk`, each with the assignment prefix. The case plan records the fixed red signal with green turn arrow, pedestrian facing, highway boundary, and the deliberately changed entry or other-device display. The arrow is not treated as pedestrian permission.

## CPU proof

`execution-manifest.json` binds each case to its own inline construction hash, offline receipt, positive and negative compatibility receipt, saved-only receipt, three physical outcome fixtures, lifecycle protocol fixture, and positive and negative independent delivery audit test. All four compatibility receipts pass current construction hashes with Lean validation, final decode, mandatory measurement, and a rejected missing-source negative. All four saved-only receipts preserve source bytes. Twelve physical fixtures demonstrate complete, incomplete, and missing-evidence classification. Four audit positives pass 900-frame/four-video source-shaped checks, and four negatives reject unreleased receipts. Nine unit tests and the canonical semantic stage pass. `cpu-selected-validation.json` reports semantic, compatibility, physical, and delivery validators passing; its downstream selected structure probe passes. The real selected execution validator rejects the incomplete sweep.

The diagnostic 900-frame fixtures are synthetic. They do not establish original CARLA motion, actual signal/device assets, highway dedication, frame pixels, permission under NRS 484B.283, or local acceptance. `proof-summary.json` records the exact case hashes and proof counts.

## Source dependency and next local step

Frozen `inputs/testing__C227824__NRS-484B-307-9c__pedestrian/evidence.json` has `recordings: []`. Its judgment range inventory contains no exact C227824/NRS-484B-307-9c/pedestrian range. The missing source is a reviewed original signalized highway/OpenDRIVE packet with Native red and green-turn-arrow assets, other-device authority/display, pedestrian facing and crossing route, plus source-supported feasible controls and legal review for the NRS 484B.283 permission sweep. The package requires those sources before expanding the sweep or asserting readiness. Once supplied, run original Native attempts, owner release, saved processing, four exact delivery audits and three comparison audits, then the exact strict gate. `gpu-queue-proposal.json` lists commands but is explicitly not dispatchable.
