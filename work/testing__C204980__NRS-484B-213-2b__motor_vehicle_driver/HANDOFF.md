# C204980 railroad grade-crossing delivery handoff

Status: CPU delivery prepared. Exact scoped strict gate passed on 2026-11-26:

`.venv-cpu/bin/python worker_check.py --assignment testing__C204980__NRS-484B-213-2b__motor_vehicle_driver --complete --require-delivery-ready`

This is NRS 484B.213(2)(b), with subsection (3), for motor vehicle driver in C204980. Six exact cases cover left-side approaches at 101, 100 and 99 feet; right-side approach at 99 feet; left-side crossing traversal; and the one-way exception context. Five controlled comparisons test the distance boundary, side, traversal and one-way status. The 100-foot value is statutory. Leading body to near crossing edge and centerline are documented engineering references; no synthetic measurement is a legal finding.

## CPU evidence

- Source-reviewed Native capture is gated on original highway, qualifying stationary railroad carrier, at-grade crossing, vehicle/control, centerline, road map, and four-camera setup. It refuses diagnostic fixtures as live reviewed sources.
- Twelve primary/fallback exact-case offline checks passed. Twelve positive and negative compatibility proofs passed through original-source joins, selected measurements, Native validation, Core conversion, Lean decoder, four-camera and final 900-frame decode. Synthetic diagnostic sources are marked as such.
- Six physical diagnostic proofs each distinguish complete, incomplete and missing original-index motion; six lifecycle proofs enforce encoders closed, restoration, Native exit, owner release, then saved processing.
- Six independent delivery audit protocol positives and negatives passed. Five fixed-condition/deliberate-difference comparison protocol positives and negatives passed. The production audit requires original Native provenance, preserved saved-only sources, full decoded video, actual pixel review and measured physical completion.
- `cpu-tests-nov26.log` records 12 passing unit tests. `cpu-preflight-nov26.log` records passing pinned runtime preflight. The assignment-scoped strict gate exited 0 after all returned proof files were bound.

`execution-manifest.json` binds every construction, fallback, offline, physical, compatibility, delivery and saved-only post-capture command. `gpu-queue-proposal.json` gives the six exact local commands and five independent comparison audit commands for lead integration. The first case is `left_101ft`; the queue proposal includes `--review-archive /external/archive` for final acceptance.

## Local realization still required

The authorized local run must select a genuinely reviewed railroad grade crossing and confirm actual CARLA motion, source capture, pixels, physical station/side/traversal, all original participants and frame joins. Saved-only processing begins after Native exit and owner release. The independent delivery auditor must then review original sources and pixels and leave unresolved legal judgments explicit. No accepted recording or physical success is claimed from these CPU fixtures.
