# training__C230222__NRS-484B-600-1e__motor_vehicle_driver

Status: partial. The 78, 80 and 82 mph cases remain unselected planning probes. No Native execution, legal verdict or accepted recording is claimed.

## Exact source and existing evidence

NRS 484B.600(1)(e) prohibits driving or operating a vehicle at a rate greater than 80 mph in any event. The frozen C230222 cell is road / travel / curb with a motor vehicle driver. The frozen membership lists three accepted recordings for requested below, at and above settings. `inputs/training__C230222__NRS-484B-600-1e__motor_vehicle_driver/review-context/review.json` lists those recordings with empty `receipt_sources` and no judgments. Its descriptions are controller requests, not measured Native speed. Their statutory equivalence and source-backed reuse remain unverified; replay of those originals is not planned.

## Current CPU construction

`native/speed_measurement.py` is a saved-source meter for a complete 30-second, 20 Hz trace. It hashes the source, verifies contiguous frame/time and subject identity, derives mph from the three-axis velocity, cross-checks pose displacement, and reports the peak speed with a measurement uncertainty interval. It separates measured above, measured not above and unresolved at the 80 mph boundary. It makes no legal or physical acceptance conclusion.

`native/speed-measurement-proof.json` binds the meter and seven passing positive/adversarial tests. The diagnostic 78, 80 and 82 mph rows are labeled `synthetic_native_sample`; they are not original Native observations. Run the test with `.venv-cpu/bin/python -m unittest discover -s work/training__C230222__NRS-484B-600-1e__motor_vehicle_driver/native -p test_speed_measurement.py -v`.

## Remaining worker-owned CPU work

Review the three accepted recordings against source-hashed receipt evidence if available. If they do not establish the whole comparison, select only uncovered cases. Construct exact road/controller/camera bundles with one primary and three distinct tested fallbacks per selected case. Bind a current-runtime execution manifest, run exact offline and positive/negative compatibility checks, saved-only processing with all four source-camera videos, semantic stage validation, independent delivery and comparison audits. Check the exact assignment with `.venv-cpu/bin/python worker_check.py --assignment training__C230222__NRS-484B-600-1e__motor_vehicle_driver --complete --require-delivery-ready` before promoting to ready. Original physical speed, pixels and territorial applicability require later local review.
