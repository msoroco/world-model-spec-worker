# training__C230281__NRS-484B-360-1__motor_vehicle_driver

Status: ready for CPU delivery preparation. The exact assignment strict gate passed on 2026-11-26. No CARLA execution, accepted recording, or legal verdict is claimed.

## Exact scope and selected comparison

NRS 484B.360(1) limits a school bus transporting pupils to or from school to 55 mph. The frozen cell is road / travel / school_bus with actor motor_vehicle_driver. Three selected Native cases request 53, 55, and 57 mph on the same route and compare the original bus velocity recorded at 20 Hz for 600 frames. The measured speed, bus classification, judged driver's relationship to the bus driver, pupil presence, and school trip purpose remain separate source observations. A requested controller speed is never treated as a measured result or legal conclusion.

## CPU evidence

Each selected case has a current-runtime offline Native construction pass, public positive and missing-source negative compatibility probes, recorded-only saved processing, source-speed diagnostic, physical and lifecycle fixture checks, and independent delivery audit. The canonical semantic validator passed seven stages. The controlled comparison audit passed across the three selected speeds. The execution manifest binds exact case construction and proof receipts; result.json lists the offline proof log hashes. The scoped strict command exited 0:

.venv-cpu/bin/python -B worker_check.py --assignment training__C230281__NRS-484B-360-1__motor_vehicle_driver --complete --require-delivery-ready

The diagnostics are synthetic source-shaped samples for CPU contract testing. They do not prove the original CARLA bus design, actual driver and passenger identities, route/trip purpose, physical speed, or legal outcome. Those require original-source review and local Native delivery. The route survey and passenger-trip review are required original-source inputs in the selected runner.

## Delivery and limits

The Native runner is native/bus_capture.py, with four pinned views in this order: overview, approach, reference_corner, driver_reference. It records joined Native motion, source video, evidence, and capture seals; native/finalize.py processes only saved sources. Use the selected execution-manifest.json and semantic-proposals.json for delivery. The frozen accepted membership IDs have no source-file inventory in this package, so no equivalence or reuse is asserted. Original physical and legal acceptance remains pending.
