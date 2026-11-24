# LVMC 11.52.130(A)(12) at C229397 — partial CPU construction checkpoint

The fixed road/park/crosswalk cell, exact source text and two controlled case IDs are preserved. No accepted recording is reused. The case plan keeps the introductory conflict, law and officer/device direction exceptions unresolved rather than treating a geometry-only park as a legal outcome.

## New construction and proof

- `native/geometry.py` authors a 100 m road with parking lane and an OpenDRIVE crosswalk object proposal. `native/runner.py` drives and brakes the subject before that crossing, surveys the parking lane and requires original Native `get_crosswalks()` readback. It retains 600 frame identities at 20 Hz, four FFV1 camera streams, measured vehicle pose and extent, and world restoration. Its inventory leaves actual marked paint and legal exception sources unverified.
- `crosswalk_measure.py` computes center-to-crosswalk, full-body-to-crosswalk and along-road body gaps per frame. The 20 ft value is converted exactly to 6.096 m for diagnostics only; no legal measurement convention or verdict is asserted. The regular and optimized proof tests two controlled synthetic positions with 12 m versus 3 m body gaps, and rejects missing marking/direction sources, changed identity and short frame count.
- `finalize_crosswalk.py` joins original saved pose and FrameMap identities, checks all four camera frame identities and invokes the source-bound measure. `prove_saved.py` executes a positive saved-only fixture and rejects missing camera, missing marked-crosswalk source, altered Native frame and missing pose file. It does not decode video or claim physical acceptance.
- Both exact primary construction drafts passed pinned `runtime.py offline`; assignment-scoped `worker_check.py --complete` passed. Strict scoped ready gate fails because result status truthfully remains partial.

Construction hashes: controlled_1 `af6aebbe6a9881883818b3e48663565b5d57213cfbe40a5585ae1f4a51ee907c`; controlled_2 `9f99a57bfe85054b4af21d436eed5b5d6b2e9dd4dbb908f851cf40b8de8c8057`. Distance proof `5dca9138d35c3cc4f1d03d8fddaeb856b86b57a61c3f7372e2de3fd98afc5367`; saved join proof `7eb5abd53505cb8d82d3da41f58fec512c35d64417eb846ad7cbe8082dcfaded`; both offline logs `f91190d71b4363b620533e06616bbc2b78c7042426d47f0ffe765393ea04fedd`; scoped check `b680c4d036b55bfd848522b7bd3b793bb9941df802c9c57e4b7ff022b2740635`.

## Remaining worker-owned CPU work

Source-bind actual painted marking and complete crosswalk extent, jurisdiction, responsible person, traffic-conflict necessity, law compliance and any police/device directions. Complete the stop and stand statutory alternatives and each applicable exception in controlled cases. Finish selected execution manifest, three distinct tested fallbacks per selected case, runtime process-saved/finalizer integration, positive/negative compatibility with four-camera video decoding, independent acceptance/comparison audits, semantic proposals and queue entries. Rebind affected receipts and run the strict ready gate after these proofs exist. Native physical results, pixels and legal sufficiency remain unobserved.
