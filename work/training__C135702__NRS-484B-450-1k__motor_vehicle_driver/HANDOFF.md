# C135702 — NRS 484B.450(1)(k)

Status: partial implementation checkpoint; no delivery or legal outcome is claimed.

The selected witness is parking near a highway obstruction on a narrow road. The planned pair changes the remaining opening and measured passing-traffic response while holding road and excavation geometry fixed. `native/measure_obstruction.py` reads exactly 600 original-shaped Native samples at 20 Hz. It checks a stationary ego body alongside the excavation, computes the largest free transverse opening from sampled full-body rectangles, records passing traffic speed/halt frames, and requires all four exception flags and their source-review receipts on every sample. It returns continuous measurements and leaves the statutory “would obstruct traffic” judgment unresolved.

`native/prove_obstruction.py` constructs two 600-frame synthetic source files and checks 0.5 m opening/600 halt frames against 2.2 m opening/0 halt frames. Six negatives reject a missing exception flag, incomplete police-direction source review, passing-body teleportation, speed/body-motion mismatch, source-hash mismatch, and missing original source. The positive passing vehicle crosses the obstruction longitudinal station, while the halted vehicle stays upstream. This is a kinematic check on synthetic rows, not evidence of real traffic response. Run `.venv-cpu/bin/python work/training__C135702__NRS-484B-450-1k__motor_vehicle_driver/native/prove_obstruction.py`. The proof output is `native/obstruction-proof.json`. These synthetic rows establish software behavior only; they are not CARLA observations, physical cause confirmation, or a legal verdict.

Files and SHA-256:
- `native/measure_obstruction.py`: `313cd2ccd43752c5f97edf817a3d85f5f960ad064e05fb5f07beca5d1c88414c`
- `native/prove_obstruction.py`: `1e038148c8276d2eeab7ca56d2f576bc3a020dfc59809c04a09b91124b735b30`
- `native/obstruction-proof.json`: `99e2430af036d3a9ed1f680d7ec7a16b74bd77ca3028a9b1a71a9e36c721f1b1`

Required CPU work remains: author executable Native road, excavation, ego parking and passing-traffic construction with four synchronized cameras; source-bound original capture and saved finalization; exact selected semantic proposals and up to risk-justified candidates; offline and positive/negative compatibility proofs for each; independent saved audit and comparison isolation audit; exception authority and residual-width/delay review. The zero accepted membership rows remain unchanged. Run the assignment strict gate only after all CPU proofs pass.
