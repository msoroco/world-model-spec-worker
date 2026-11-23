# NRS-484B-300-1 at C10389

Actor: `motor_vehicle_driver`. Frozen cell: `alley` / `travel` / `traffic_control_device`.

Exact statutory source: NRS 484B.300(1). The law text is retained in `case-plan.json`; extracted summary status is `recovered_requires_source_review`. Witness branches: Device-governed alley travel..

Controlled planning variable: `obedience_to_official_device`. Proposed requests: obey the exact applicable official device instruction; disobey the same applicable official device instruction. These are scene/controller targets, not observed conduct or legal verdicts.

Statutory alternatives and exceptions still to cover or disposition: NRS 484B.307 signal-specific rule; police officer direction; official placement provenance.

Accepted membership: 0 distinct recording IDs. Their contents and exact source-hashed equivalence are unavailable in this checkout, so reuse is not claimed.

Current CPU work: `native/device/` contains eight unselected source-bound OpenDRIVE stop-device requests for the obey/pass pair, primary and three distinct fallbacks. Each request now spans 600 frames at 20 Hz (30 seconds) on a 300 m alley. The original CARLA capture code records overview, approach, reference-corner and driver-reference FFV1 source videos plus a composed `raw.mkv`. Its saved processor requires those five videos at the expected dimensions, 20 Hz, 600 decoded frames, and byte hashes for each source view in the separate frame review. The authored signal is not proof of official placement. The 484B.307 rule, police direction and placement provenance remain separate pending statutory topics.

Current-runtime CPU proof: `.venv-cpu/bin/python runtime.py preflight` passed. Rebuilt the eight copied bundles and checked 8 positives/64 tamper negatives; the independent package audit recomputed 4,800 requested rows. The synthetic raw-to-saved route checked 8 positives/88 tamper negatives plus two measured fallback triggers; the independent saved audit recomputed 4,800 frame joins. The pinned `runtime.py offline` check passed all eight constructions and 24 tests; its independent audit verified 104 materialized source files and an altered-construction rejection. `prove_video_profile.py` generated four short synthetic full-resolution FFV1 views under `.runtime-work/`, composed and fully decoded the 3840x1800 primary stream at 20 Hz. These are CPU software proofs only; see `native/device/offline/current-refresh-proof.json` (SHA-256 `bb1e0c8e04e5718780003d90d28dffbfc111cbe551b62a4c876d030be7a53e58`) and its bound receipt hashes. `.venv-cpu/bin/python worker_check.py --assignment training__C10389__NRS-484B-300-1__motor_vehicle_driver --complete` passed the partial package's static checks.

Current limitation: original Native sign readback, full synchronized original videos, source-hashed human review, physical stopping and crossing, official placement, accepted equivalence and legal comparison are unverified. The current saved path is a package-local diagnostic and still needs selected-case `process-saved` integration, all exact selected receipts, and comparison audit. No candidate is selected and the assignment remains partial.

Resume CPU construction: implement one selected exact case's current-runtime saved finalizer, positive/missing-source process-saved proof, independent delivery audit and comparison isolation. Then expand the paired case and risk fallbacks, rebinding all affected receipts. Run the assignment-scoped strict gate before any ready promotion. Local original Native execution and human frame review follow CPU preparation; independently establish official placement and statutory exception context before legal comparison.
