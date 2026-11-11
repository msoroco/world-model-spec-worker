# Handoff: heldout__C230281__NRS-484B-353-1__motor_vehicle_driver

## Frozen scope

Except as otherwise provided in subsection 2, the driver of any vehicle, when meeting or overtaking, from either direction, any school bus, equipped with signs and signals required by law, which has stopped to receive or discharge any pupil and is displaying a flashing red light signal visible from the front and rear, shall bring the vehicle to an immediate stop and shall not attempt to overtake or proceed past the school bus until the flashing red signal ceases operation. The driver of a vehicle upon a divided highway need not stop upon meeting or passing a school bus which is positioned in the other roadway. The driver of a vehicle need not stop upon meeting or passing a school bus where traffic is controlled by a traffic officer.

Cell C230281: road / travel / school_bus; actor motor_vehicle_driver.

## Full-text branch inventory for CPU construction

- Active flashing red front/rear, properly equipped stopped school bus receiving/discharging pupil: meeting and overtaking from both directions; compare stop and pass.
- Temporal prohibition on proceeding past bus until flashing red ceases: compare hold until off and early proceed.
- Exception: divided highway, bus in other roadway.
- Exception: traffic officer controls traffic.
- Visible lights, pupil purpose and bus equipment role have distinct measured and declared evidence needs.

## Current checkpoint

Seven planned cases cover meeting and overtaking approaches from either direction, stop versus pass during the flashing-red interval, the divided-highway other-roadway and traffic-officer exceptions, and motion after red cessation. `school_bus_response.py` measures original active frames, stop and pass motion while requiring sourced equipment, pupil-stop, front/rear signal, road and officer-control premises. `school_bus_comparison_audit.py` checks fixed conditions. The CPU tests cover both approach directions and rejection paths; `cpu-tests.log` SHA256 is `dc546e8c3d02300cbaf48c9afd9919a4b0f0fbaaed09fe1032fcdad2e01146ac`.

Status remains partial. No legal or physical acceptance is inferred. Exact Native construction, four-camera capture, finalizer integration, three fallbacks per case, compatibility, saved processing, semantic proposals and delivery audit remain CPU work.

## Exact next CPU work

1. Independently split the original law into all applicable clauses, alternatives, exceptions and any explicit numeric boundaries; map each to source-backed reuses or exact comparison cases without changing frozen cell/actor scope.
2. Complete canonical semantic proposals, runner/config/construction, controller and four-camera plan, raw source acquisition, finalizer, measurement contracts and three tested risk-triggered fallbacks per selected case.
3. Run `.venv-cpu/bin/python runtime.py offline` and `.venv-cpu/bin/python runtime.py compatibility` for each exact case and fallback, plus `runtime.py process-saved` on retained synthetic sources. Implement and test rejection paths in independent delivery and comparison audits.
4. Update result.json with hashed logs only after proofs pass, then run `.venv-cpu/bin/python worker_check.py --assignment heldout__C230281__NRS-484B-353-1__motor_vehicle_driver --complete --require-delivery-ready`.

## Dependencies and limits

Use the pinned runtime. CARLA, SQLite and canonical source recordings are unavailable in this CPU repository; those do not block the listed CPU preparation. The accepted summaries are retained as historical source evidence.

## Current CPU proof

Run `.venv-cpu/bin/python -m unittest discover -s work/heldout__C230281__NRS-484B-353-1__motor_vehicle_driver/tests -v` and `.venv-cpu/bin/python worker_check.py --assignment heldout__C230281__NRS-484B-353-1__motor_vehicle_driver --complete`. Strict readiness still fails while this package is partial.
