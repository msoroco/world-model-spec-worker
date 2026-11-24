# NRS-484B-223-1b at C245490

Actor: `motor_vehicle_driver`. Frozen cell: `same_direction_multilane` / `change_lane` / `lane_marking`.

Exact statutory source: NRS 484B.223(1)(b). The law text is retained in `case-plan.json`; extracted summary status is `recovered_requires_source_review`. Witness branches: Both conjunctive prerequisites before movement from the occupied lane..

Controlled planning variable: `prior_signal_before_lane_departure`. Proposed requests: driver signals and checks safe gap before departing marked lane; driver departs same lane without prior signal. These are scene/controller targets, not observed conduct or legal verdicts.

Statutory alternatives and exceptions still to cover or disposition: two or more clearly marked same-direction lanes; independent safety ascertainment; unsafe-gap branch.

Accepted membership: 10 distinct recording IDs. Their contents and exact source-hashed equivalence are unavailable in this checkout, so reuse is not claimed.

Historical baseline gap before this checkpoint: no executable construction or measured source-trace diagnostic existed. The current draft and diagnostic are documented below; the selected exact delivery path and its remaining proofs are still incomplete.

Original resume list (partly advanced below): reconcile every branch against exact text and physical cell; promote and test selected Native routes and controllers, and execute pinned-runtime compatibility, saved-only and independent audit proofs. Mark `ready` only after all CPU proofs pass.

## 2026-11-23 CPU construction and source-trace checkpoint

Pinned `.venv-cpu/bin/python runtime.py preflight` passed. `native/measure_lane_change.py` measures 600 synchronized 20 Hz source rows. It tests the two-or-more same-direction marked-lane activation, first ego-body departure from the retained occupied-lane boundary, whether the target-direction indicator began before departure, signal lead time, target-lane surface gap, and time to conflict where closing speed is positive. It keeps driver safety ascertainment and legal verdict unobserved. `native/prove_lane_change.py` binds the frozen assignment SHA and produces four 600-frame diagnostic traces (early signal, late signal, small gap, one lane) plus three rejected-source tests. The proof is `native/lane-change-diagnostic-proof.json` (SHA-256 `f5bbf532ceaeab9964750accb990e067fd5aa1ea01a9a03158f46e43705a2a36`). These are labelled synthetic Native samples and do not prove the planned physical cases.

`native/build_draft.py` builds one exact unselected Native proposal, `signal_before_draft`, with 600 synchronous ticks, signal request before steering, a controlled left-lane departure request, a target-lane vehicle, four RGB source cameras, FrameMap, original motion trace, encoder checks and world restoration. Pinned `runtime.py offline` passed with five CPU checks (runner check plus four unit tests). Construction SHA-256 `25332da455f1556505ef65ece21d79551c7676aa4be6869781d6c659a535ef66`; manifest SHA-256 `1ff6354eebb5dd4e49ae659d5b8c46a11f78f4048c4a95bcb0dff85b15f5b76b`; hashed log and command are in `native/draft-offline-proof.json`.

The draft requires map review before selection: its occupied-lane center is sampled at the current OpenDRIVE road station and requires Native road-station review, the signal state needs independent pixel confirmation, and the target vehicle gap needs original actor and camera review. The current plan's two signal cases do not cover independent safety ascertainment or the unsafe-gap comparison. Accepted membership alone is insufficient for source-hashed equivalence. Finish exact selected constructions, original-source measurement/finalization, compatibility and saved-only proofs, fallback assessments, independent audits and statutory branch comparisons before trying the assignment-scoped strict gate. Physical outcomes and acceptance remain unverified.

The final draft offline receipt SHA-256 is `2dc50e7c71d0bbd6335ad8d0638dfc4ca2394466708443c463ea5785721172cd`; its log SHA-256 is `051b57dc3f8ec1a587472c4b1b1adbdc1479df70bbb5735f529662be69f32f8f`. The earlier draft hashes in this handoff have been superseded by the final road-station geometry revision.
