# training__C378131__LVMC-11-60-030-A2__bus_driver

Status: partial. No selected delivery case, accepted recording or legal verdict is claimed.

## Source and scope

LVMC 11.60.030(A)(2): The operator of a bus, other than a tour bus, shall: Not stop such vehicle upon any street at any place for the purpose of loading or unloading passengers or their baggage other than at a bus stop, bus stand, passenger loading zone or the origin or destination point for the route to which such vehicle is assigned which has been designated in accordance with Section 11.60.010 [DEF-LVMC-11-60-010], except in case of an emergency.

Cell: business_district / load_unload / bus_route_terminus; actor: bus_driver. Frozen witness count: 1. Membership rows: {'full-train': 0}. Membership alone does not prove coverage or reuse. Exact source and topic hashes are in `case-plan.json`.

## Proposed comparison

non-tour route bus loads passengers; same assigned route and purpose Vary only `bus_loading_location` (category) across ['designated_terminus', 'undesignated_street']. Record route assignment/designation authority, stop, passenger board/alight and place. The definitions are not selected recordings, and requested settings are not measured results.

## New CPU construction and proof

`analysis/branch-expansion.json` quotes and separately plans bus stop, bus stand, passenger loading zone, route origin, route destination, emergency exception and tour-bus exclusion. It preserves the existing terminus versus undesignated street pair and leaves every added branch unselected pending catalog and designation-source review. It asserts no legal cutoff or accepted evidence.

`analysis/bus_loading.py` is a source-shaped measurement path for the exact statute. It checks non-tour route-bus identity, assigned route, street and zone identity, a source-hash reference for designated places, original frame sequence and 20 Hz timing, four source-camera joins, speed/stop, passenger-door state, boarding and occupied zone. Its output retains the observed event counts and leaves emergency and legal judgment unresolved. A formatted designation reference is only a declared source; the referenced authority document still needs independent verification. `analysis/test_bus_loading.py` passes a 600-frame, 30-second `synthetic_native_sample` diagnostic and rejects missing camera, door, designation reference, route binding, emergency context and short duration. Log SHA-256: `68b393af39097679872421649111481f4eb768b6cc8e9681ccedc342f4143963`. Invented fixture motion is not original Native velocity.

The assignment-scoped checkpoint `.venv-cpu/bin/python worker_check.py --assignment training__C378131__LVMC-11-60-030-A2__bus_driver --complete` passes static checks after this update. The strict ready gate has not passed.

## Remaining CPU work

Verify the designated-place authority and exact 11.60.010 dependency from frozen source material. Review compatible catalog cells for the added alternatives, keep incompatible branches separate, and create canonical semantic stage proposals. Build exact selected-case Native construction, primary and three distinct risk fallbacks where required by the active delivery contract, synchronized four-camera capture, source-bound saved finalization, positive/negative compatibility, and independent delivery and comparison audits. Run the scoped strict gate before any ready label. Original physical stop/loading behavior, pixels and any emergency facts require later source review; legal judgment remains separate.
