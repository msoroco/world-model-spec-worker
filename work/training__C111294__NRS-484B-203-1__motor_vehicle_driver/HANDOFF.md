# NRS 484B.203(1) at C111294

Frozen cell: opposing vehicle meeting on a one-lane-each-direction road. Exact statutory source and the two proposed 0.45/0.55 footprint-fraction probes are in `case-plan.json`. Two full-train membership IDs are unreviewed; no equivalence or reuse receipt is claimed.

Built source-bound 30-second, 600-frame, four-camera meeting meter (`measure_meeting.py`) and authored two-direction OpenDRIVE road plus paired ego/oncoming requests (`meeting_scene.py`). `meeting-measurement-contract.json` maps all frozen observation terms to original map, pavement, body and motion sources. CPU proof `meeting-proof.json` distinguishes 0.45/0.55 ego right-half body fractions and passing gaps, with seven negative controls. `meeting-scene-proof.json` tests the fixed road/oncoming/camera conditions and requested lateral placement, with four negative controls. Fixture hashes and motion are invented; authored geometry has not executed in Native.

The statute requires keeping right and giving at least one-half the paved portion as nearly as possible. The body's fraction in the right half is only a measurement diagnostic; it is not the statutory allocation and no legal verdict is inferred. Original road edges, lane count, physical constraints and both vehicle bodies need independent source review. The two planned cases remain unselected.

Next: create four distinct source-preserving Native candidate constructions per selected case, run pinned offline and positive/negative compatibility, capture four source cameras/600 frames, then actual recorded-only saved processing and independent acceptance/comparison audits. Keep partial until scoped strict readiness passes.
