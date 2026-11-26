# testing__C262661__NRS-484B-363-1__bus_driver

Status: partial, source-gated CPU construction and analysis checkpoint. No original CARLA recording or legal/physical acceptance is claimed.

## Frozen scope and selected coverage

Assigned branch: Motor bus in a school zone with children. Law: NRS 484B.363(1) and beacon definition in subsection (9). Cell C262661, bus_driver. Frozen accepted recordings: zero. The 15-mph rule, four exceptions and two-or-more alternating-yellow-light definition are mapped to seven selected requirement dispositions in `case-plan.json`; all source facts remain independently reviewable.

Exact cases (15):
- `testing__C262661__NRS-484B-363-1__bus_driver__beacon_flashing_14_9`
- `testing__C262661__NRS-484B-363-1__bus_driver__beacon_flashing_15_0`
- `testing__C262661__NRS-484B-363-1__bus_driver__beacon_flashing_15_1`
- `testing__C262661__NRS-484B-363-1__bus_driver__no_session_15_1`
- `testing__C262661__NRS-484B-363-1__bus_driver__after_operation_15_1`
- `testing__C262661__NRS-484B-363-1__bus_driver__before_next_start_15_1`
- `testing__C262661__NRS-484B-363-1__bus_driver__beacon_class_not_flashing_15_1`
- `testing__C262661__NRS-484B-363-1__bus_driver__beacon_class_flashing_15_1`
- `testing__C262661__NRS-484B-363-1__bus_driver__nonbeacon_sign_off_15_1`
- `testing__C262661__NRS-484B-363-1__bus_driver__nonbeacon_sign_on_15_1`
- `testing__C262661__NRS-484B-363-1__bus_driver__beacon_one_yellow_15_1`
- `testing__C262661__NRS-484B-363-1__bus_driver__beacon_non_alternating_15_1`
- `testing__C262661__NRS-484B-363-1__bus_driver__outside_zone_15_1`
- `testing__C262661__NRS-484B-363-1__bus_driver__no_children_15_1`
- `testing__C262661__NRS-484B-363-1__bus_driver__ordinary_car_15_1`

Exact controlled comparisons (12):
- `below_versus_at_15_mph`: `testing__C262661__NRS-484B-363-1__bus_driver__beacon_flashing_14_9`, `testing__C262661__NRS-484B-363-1__bus_driver__beacon_flashing_15_0`
- `at_versus_above_15_mph`: `testing__C262661__NRS-484B-363-1__bus_driver__beacon_flashing_15_0`, `testing__C262661__NRS-484B-363-1__bus_driver__beacon_flashing_15_1`
- `school_not_in_session`: `testing__C262661__NRS-484B-363-1__bus_driver__beacon_flashing_15_1`, `testing__C262661__NRS-484B-363-1__bus_driver__no_session_15_1`
- `half_hour_after_operation`: `testing__C262661__NRS-484B-363-1__bus_driver__beacon_flashing_15_1`, `testing__C262661__NRS-484B-363-1__bus_driver__after_operation_15_1`
- `half_hour_before_next_operation`: `testing__C262661__NRS-484B-363-1__bus_driver__beacon_flashing_15_1`, `testing__C262661__NRS-484B-363-1__bus_driver__before_next_start_15_1`
- `class_hours_beacon_flashing`: `testing__C262661__NRS-484B-363-1__bus_driver__beacon_class_flashing_15_1`, `testing__C262661__NRS-484B-363-1__bus_driver__beacon_class_not_flashing_15_1`
- `nonbeacon_sign_time_indication`: `testing__C262661__NRS-484B-363-1__bus_driver__nonbeacon_sign_on_15_1`, `testing__C262661__NRS-484B-363-1__bus_driver__nonbeacon_sign_off_15_1`
- `two_yellow_light_definition`: `testing__C262661__NRS-484B-363-1__bus_driver__beacon_flashing_15_1`, `testing__C262661__NRS-484B-363-1__bus_driver__beacon_one_yellow_15_1`
- `alternating_flash_definition`: `testing__C262661__NRS-484B-363-1__bus_driver__beacon_flashing_15_1`, `testing__C262661__NRS-484B-363-1__bus_driver__beacon_non_alternating_15_1`
- `designated_zone_boundary`: `testing__C262661__NRS-484B-363-1__bus_driver__beacon_flashing_15_1`, `testing__C262661__NRS-484B-363-1__bus_driver__outside_zone_15_1`
- `children_presence_is_not_independent_exception`: `testing__C262661__NRS-484B-363-1__bus_driver__beacon_flashing_15_1`, `testing__C262661__NRS-484B-363-1__bus_driver__no_children_15_1`
- `bus_versus_other_motor_vehicle`: `testing__C262661__NRS-484B-363-1__bus_driver__beacon_flashing_15_1`, `testing__C262661__NRS-484B-363-1__bus_driver__ordinary_car_15_1`

## Current construction and CPU proofs

The selected source-gated runner, 900-frame/20-Hz four-camera Native capture, bridge, source-bound analysis, saved finalizer, independent original delivery and comparison audits, and exact queue proposal are implemented. The original school site/operator packets and physical CARLA recording remain local acquisition inputs; no physical acceptance or legal verdict is claimed by CPU diagnostics.

- Exact selected cases: 15. Every case has a current construction hash, fresh offline proof, source-inventoried diagnostic recipe, selected-requirement measurement contract, positive and missing-source negative compatibility receipt, three physical outcome fixtures, Native owner-release lifecycle proof, and positive/negative independent diagnostic delivery audit.
- Exact plan comparisons: 12. Every pair passed diagnostic requested-intervention isolation; swapped-case negative tests were rejected. `comparison_audit.py` independently checks original source hashes, fixed map/zone/route and actual saved observations in the local delivery path.
- Semantic proposals: pinned `semantic_delivery.validate` accepted the relevance pair, exact-law template, eight judgment-observable entries, binding and 16-case proposal (one planning baseline plus 15 selected cases). Eight judgment sweep plans remain explicitly source-gated pending reviewed original school records; they assert no judgment cutoff.
- Saved processing: `saved_finalizer.py` recomputes 600 steady-window samples from 900 saved Native frames and rejects short capture. `delivery_audit.py` requires exact 15 original source inventories, recomputes each saved result and runs all 12 original comparisons. Synthetic fixtures are rejected as original delivery evidence.
- Focused tests: 21 passed in `cpu-school-tests-nov26.log`; runtime verify and preflight passed. Pinned scoped strict gate passed with exit 0, proving `delivery_prepared` readiness for this assignment.

Current source/proof hashes:
- `case-plan.json` SHA-256 `56f082d960a068a05bdd1787a3c6b03c7e6f1f5e6cf014843fbbe11db35e96af`
- `construction.json` SHA-256 `f7235f8231e54001c6af0a8636943c0922bf311974cde8411168b8223c8a6a46`
- `execution-manifest.json` SHA-256 `8ab6b217e46680cef8476fed02d4e1ce589548368b41f110b1d40cbd9091cdb8`
- `gpu-queue-proposal.json` SHA-256 `0ca2aa4fe47bd74e10efc07190a051e3a2780c5908a0fd026755b911106396d3`
- `proposals/semantic-index.json` SHA-256 `73a2d870eef0990fbae2fc3278e5bc8e5d92ee9a2fa859676044845a228276cc`
- `result.json` SHA-256 `63688c5bea5d6c2233343012e6137ad901df34b04376b0e0654526598bb10b88`
- `analysis.py` SHA-256 `1039c7f811f872dbd4ab7b3a993c774b16344892068f724df515c506ad1fc5f5`
- `native_output_bridge.py` SHA-256 `559d6e0a4ddc3bcf0a10f252ffb7c9b723022e74cd75a5abcc3b79fadef94465`
- `diagnostic_delivery_audit.py` SHA-256 `dcc698e21c42d7b0c86fe7f8c96c79e6d22525747a5c7d51726684e769009f4e`
- `delivery_audit.py` SHA-256 `fdce41f2175d80a43a51f5371484f91135b5fe8c35533c1aae6ce4a626c90a11`
- `diagnostic_comparison_audit.py` SHA-256 `69d1699514c6584b297dc018b92d3a5b3db5c99523eaf88d651f28ff20191865`
- `cpu-school-tests-nov26.log` SHA-256 `ecfa7151b7221d954e9a018fedfc2e0485532bf1e8fc1e831ae7b1f1a9030208`
- `cpu-strict-ready.log` SHA-256 `5a8a41eecd92d272be71cb394065baa5466c89b04d79dc3bc55f408fe79e2edb`

## Local delivery and resume

The lead owns integration of `gpu-queue-proposal.json` into the shared queue and checkpoint publication. Its 15 case rows and 12 comparison rows contain exact production commands. Start the first selected local job using `result.json:first_gpu_delivery_command` with `CARLA_PYTHON`, `CARLA_HOST`, `CARLA_PORT`, `DB`, `RUN` and `JOB_ID` set by the local operator. Source packet path is supplied through `SCENARIO_SCHOOL_SITE_PACKET` and reviewed before acquisition. Keep Native owner release before saved processing; use the original index with `delivery_audit.py --case ID --index PATH --output PATH` and `comparison_audit.py` for accepted local data. Diagnostic receipts only establish CPU software compatibility.

To recheck current preparation, export `SCENARIO_PIPELINE_OUTPUT_ROOT` and `TMPDIR` to a directory under `.runtime-work/`, then run `.venv-cpu/bin/python worker_check.py --assignment testing__C262661__NRS-484B-363-1__bus_driver --complete --require-delivery-ready`. The passing output is retained in `cpu-strict-ready.log`. Run the 21 focused tests with `.venv-cpu/bin/python -m unittest discover -s work/testing__C262661__NRS-484B-363-1__bus_driver/tests -v`.
