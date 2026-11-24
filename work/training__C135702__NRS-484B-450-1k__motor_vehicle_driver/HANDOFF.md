# C135702 — NRS 484B.450(1)(k)

Status: partial implementation checkpoint; no delivery or legal outcome is claimed.

The selected witness is parking near a highway obstruction on a narrow road. The planned pair changes the remaining opening and measured passing-traffic response while holding road and excavation geometry fixed. `native/measure_obstruction.py` reads exactly 600 original-shaped Native samples at 20 Hz. It checks a stationary ego body alongside the excavation, computes the largest free transverse opening from sampled full-body rectangles, records passing traffic speed/halt frames, and requires all four exception flags and their source-review receipts on every sample. It returns continuous measurements and leaves the statutory “would obstruct traffic” judgment unresolved.

`native/prove_obstruction.py` constructs two 600-frame synthetic source files and checks 0.5 m opening/600 halt frames against 2.2 m opening/0 halt frames. Four negatives reject a missing exception flag, incomplete police-direction source review, source-hash mismatch, and missing original source. Run `.venv-cpu/bin/python work/training__C135702__NRS-484B-450-1k__motor_vehicle_driver/native/prove_obstruction.py`. The proof output is `native/obstruction-proof.json`. These synthetic rows establish software behavior only; they are not CARLA observations, physical cause confirmation, or a legal verdict.

Files and SHA-256:
- `native/measure_obstruction.py`: `71fa8492e585a6f7ce234b581082db2e33784835176f28155527d1322288d0e6`
- `native/prove_obstruction.py`: `c31aafc76aae58eba7a1502f9fbbbc4f67aca7a2a4f32574d5ce16665dcf8038`
- `native/obstruction-proof.json`: `36e9a05cc11ce83b55932ae75e940953fbc47d782daca87eeb89b4db9a45bc70`

Required CPU work remains: author executable Native road, excavation, ego parking and passing-traffic construction with four synchronized cameras; source-bound original capture and saved finalization; exact selected semantic proposals and up to risk-justified candidates; offline and positive/negative compatibility proofs for each; independent saved audit and comparison isolation audit; exception authority and residual-width/delay review. The zero accepted membership rows remain unchanged. Run the assignment strict gate only after all CPU proofs pass.
