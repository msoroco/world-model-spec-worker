# C150078 / LVMC 11.40.170 handoff

Status: partial. Exact source inventory has no accepted recording; CPU construction and proof work is in progress.

## Frozen scope and law review

The assigned cell is one-way road / park / bicycle rack, with a cycle or scooter operator. The exact text lists a roadway-against-curb placement and sidewalk placements in a supporting rack, against a building, or at the curb, followed by a least-obstruction-to-pedestrian-traffic phrase. The source witness conditionally supports rack parking and asks for original street/jurisdiction, rack support, sidewalk/curb/building boundaries, covered device and responsible person, parking and pedestrian passage. The modifier's attachment to all alternatives, street/parking definition interaction, and NRS 482.029 reference are legal review questions, not numeric cutoffs. There are zero accepted recordings and zero same-law judgment ranges in the frozen assignment's evidence and judgment files.

`case-plan.json` selects eight exact prospective cases: bicycle rack clear/narrow, electric bicycle rack, electric scooter rack, bicycle against building, bicycle at sidewalk curb, bicycle at roadway curb, and bicycle at another street location. Three comparisons cover rack pedestrian passage, covered device class, and placement alternatives. No physical observation or legal verdict is claimed.

## Implemented CPU work

`parking_source.py` admits only source-hashed, original-reviewed City one-way street, covered device, responsible person, rack, sidewalk, curb, building, pedestrian and parking history packets. `parking_measurement.py` joins source-hashed Native parking, pedestrian, video-frame and trace histories, checks actor and frame identities and observed placement, and measures descriptive parked frame count, pedestrian passage states and minimum device distance. The distance is descriptive; it is not a legal threshold. `tests/test_parking_measurement.py` has four passing focused tests, including missing-source rejection. `cpu-source-tests.log` holds the proof. Assignment-scoped `--complete` static check passed in `cpu-static.log`.

## Next CPU actions

Implement the actual CARLA-lazy actor/device/rack construction and original acquisition with four synchronized cameras and readback, write the saved finalizer result, then bind each case into construction/config/measurement contract/execution manifest and semantic proposals. Generate source-hashed textual diagnostics, run selected offline and positive/negative compatibility, saved-only, physical-completion, delivery and comparison proofs. Run the exact strict assignment gate, repair all failures, and keep status partial until it passes. Scratch is `.runtime-work/c150078-owner/`; never place diagnostics under work.

Local GPU verification still needs actual device/rack geometry, pedestrian passage and camera pixels. Original legal and source review remains unresolved.
