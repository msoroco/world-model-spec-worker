# C150072 access-aisle delivery handoff

Status: CPU delivery prepared for five exact selected cases and four controlled comparisons. The selected frozen cell is C150072, one-way road, parking in an access aisle; actor is motor vehicle driver; law is LVMC 11.52.136, “No person shall park a vehicle in an access aisle.” No accepted original recording or legal verdict is claimed.

## Exact construction

The five cases are full aisle parking, partial aisle parking, adjacent space parking, aisle loading stop, and aisle travel. Each has a materialized Native runner/config/construction, four synchronized views for 45 seconds at 20 Hz, a source-gated original site packet, measured vehicle body polygon and activity history, and recorded-only analysis. The site packet must establish jurisdiction, actual aisle marking and accessible route, adjacent designated space, one-way approach, map, vehicle, and route before Native capture. The original analyzer joins 900 frame identities/times and measures body overlap, speed, and activity. It does not infer a legal violation.

The comparisons are `full_vs_partial`, `aisle_vs_adjacent`, `park_vs_loading`, and `park_vs_travel`. `comparison_audit.py` accepts only independent original Native audit reports with identical fixed source hashes, camera plan, and duration, and requires the intended measured body/activity difference. The assignment-local `queue-proposal.json` contains the five selected rows and four comparison rows. There are no fallback candidates: the reviewed source geometry is absent, so no distinct source-grounded fallback trigger has been established.

## CPU proof

- Ten focused tests pass, including original frame and activity rejections, source-packet tamper checks, exact bundle/source binding, and four comparison contrasts.
- All five exact `runtime.py offline` constructions and pinned compatibility positive/negative receipts pass at their manifest hashes.
- All five physical/lifecycle probes pass complete, incomplete, and missing-evidence states, including Native exit, owner release, and saved-source staging.
- All five recorded-only saved replays and delivery audit positive/negative mock probes pass. Mock probes check contract wiring only; they make no physical acceptance claim.
- Direct execution-manifest, semantic-delivery, delivery-handoff, and shadow ready checks pass for all five cases. `cpu-nov25-static-current.log` records the scoped complete static gate; `cpu-nov25-tests-current.log` records the ten tests.

## Original delivery boundary

Acquire a reviewed original site packet meeting `site_review.py`; set `C150072_REVIEWED_SITE_PACKET` for the Native run. Use the canonical commands in `queue-proposal.json`. Retain actual CARLA recorder, four videos, 900 joined body/activity rows, original map and packet, Native seal/exit/owner release, saved processing receipt and full-decode receipt. An independent reviewer must inspect actual pixels and record `pixel-review.json`; `queue_delivery.py` checks those original artifacts and writes the source audit. Run the four original-only comparison audits after their case reports are accepted. Physical realization, source designation, camera visibility, loading/travel activity, and legal interpretation remain to be determined from original evidence.
