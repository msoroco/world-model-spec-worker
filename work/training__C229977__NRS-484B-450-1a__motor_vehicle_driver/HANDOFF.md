# NRS-484B-450-1a at C229977

Actor: `motor_vehicle_driver`. Frozen cell: `road` / `stop_stand` / `sidewalk`.

Exact statutory source: NRS 484B.450(1)(a); with 484B.450(3). The law text is retained in `case-plan.json`; extracted summary status is `recovered_requires_source_review`. Witness branches: Vehicle stopping or standing on a sidewalk.

Controlled planning variable: `sidewalk_vehicle_occupancy`. Proposed requests: motor vehicle stops wholly off sidewalk; same motor vehicle stops on sidewalk. These are scene/controller targets, not observed conduct or legal verdicts.

Statutory alternatives and exceptions still to cover or disposition: subsection 3 external exception; bicycle/e-bike/e-scooter nonimpeding exception; traffic conflict or direction.

Accepted membership: 0 distinct recording IDs. Their contents and exact source-hashed equivalence are unavailable in this checkout, so reuse is not claimed.

Blocker: No executable Native construction, four distinct source-preserving candidates, offline/compatibility proofs, measured-result contract, positive/negative saved fixtures, independent audit, or verified source-hashed reuse receipt has been produced. Physical realization and legal outcome are unverified.

Resume: reconcile every branch against exact text and physical cell; construct Native routes and controllers, mandatory measurement mapping, four distinct plans per selected case, and execute pinned-runtime offline, compatibility, saved-only and independent audit proofs. Mark `ready` only after all CPU proofs pass.

## 2026-11-23 CPU construction checkpoint

- `native/sidewalk_occupancy.py` (SHA-256 `28830a9f60df378ccab6805fff49b98d62211757c6a41be9c1b15a3dc9552105`) computes exact polygon overlap of raw actor footprint with an acquired sidewalk polygon over 600 joined 20 Hz frames. It requires SHA-bound map and trace packets, highway/property boundary provenance, intended pedestrian-use source, post-tick pose and velocity. It returns stop and overlap histories with null legal conclusion and null exception findings. A 0.05 m/s rest tolerance is diagnostic engineering only. Positive and negative proof: `.venv-cpu/bin/python native/prove_sidewalk_occupancy.py`, log `native/sidewalk-occupancy-proof.log` SHA-256 `536e7fd50b7417d6016a3eaa582a85abe3788371edab0def3c9f6fef46fa3b09`.
- `draft-manifest.json` binds exact **unselected** `probe_1` (off sidewalk stop request) and `probe_2` (on sidewalk stop request). Each materialized bundle contains authored OpenDRIVE driving and sidewalk lanes, a 30-second/20 Hz controller request, original post-tick body/speed extraction, four-camera plan and rejection tests. Pinned `runtime.py offline` passed for both; receipts are `draft-probe-1/offline-receipt.json` and `draft-probe-2/offline-receipt.json`, log SHA-256 `968565f1d4973f291abad743ccc51c04c80ac30eb625f1bff2428747eca3401f` and `32f05a15ccb9089ed19db02a104f1abd3eda244b4ce69f5efa071ab246012ad4`. Neither draft asserts CARLA execution or physical sidewalk realization.
- The frozen law keeps subsection 3 and general traffic conflict, law, officer and official-device exceptions separate. The bicycle, electric bicycle and electric scooter passage exception is outside this motor-vehicle actor and remains for compatible actor binding. Sidewalk legal status requires acquired highway/property context and intended pedestrian use; the authored OpenDRIVE lane label alone is insufficient.
- Remaining CPU work: implement CARLA orchestration and controlled lateral stop for each exact selected case, bind all mandatory source channels and legal contexts, run current positive/negative compatibility and saved-only finalizer, add risk-based candidates, semantic proposals and independent delivery/comparison audits. Then run assignment-scoped strict gate before ready. Actual motion/pixels and physical findings remain for local execution.
