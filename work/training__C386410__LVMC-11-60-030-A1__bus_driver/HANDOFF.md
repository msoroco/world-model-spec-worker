# training__C386410__LVMC-11-60-030-A1__bus_driver

Status: partial. No selected delivery case, accepted recording or legal verdict is claimed.

## Source and scope

LVMC 11.60.030(A)(1): The operator of a bus, other than a tour bus, shall: Not stand or park such vehicle upon any street at any place other than a bus stop, bus stand or the origin or destination point for the route to which such vehicle is assigned which has been designated in accordance with Section 11.60.010 [DEF-LVMC-11-60-010] of this Chapter.

Cell: one_way_road / stop_stand / bus_route_terminus; actor: bus_driver. Frozen witness count: 1. Membership rows: {'full-train': 0}. Membership alone does not prove coverage or reuse. Exact source and topic hashes are in `case-plan.json`.

## Proposed comparison

non-tour route bus stands on one-way street; same assigned route Vary only `bus_standing_location` (category) across ['designated_terminus', 'undesignated_street']. Record standing/parking interval, assigned route and official terminus designation. The definitions are not selected recordings, and requested settings are not measured results.

## New CPU construction and proof

`analysis/branch-expansion.json` quotes seven distinct source branches: bus stop, bus stand, route origin, route destination, standing, parking and tour-bus exclusion. The source text does not list passenger loading zone as an A1 permitted place. The added branches remain unselected until catalog and designation authority review.

`analysis/bus_standing.py` measures a 20 Hz, at least 30-second bus stationary event with original-shaped velocity, brake, driver-presence, occupied-zone and four source-camera frame joins. It checks route identity and a designation-reference hash for named zones, while leaving standing/parking interpretation and legal judgment unresolved. A formatted reference is not verified authority. `analysis/test_bus_standing.py` passes a 600-frame `synthetic_native_sample` diagnostic and rejects missing camera, brake, driver-presence, designation reference, route binding, location readback and short duration. Log SHA-256: `4ef2268b75ebc5b8c3189b52a6fd922f10805657f1872dc073c8a4ec8d0ad838`. Invented fixture motion is not original Native velocity.

The assignment-scoped checkpoint `.venv-cpu/bin/python worker_check.py --assignment training__C386410__LVMC-11-60-030-A1__bus_driver --complete` passes static checks. The strict ready gate has not passed.

## Remaining CPU work

Verify the 11.60.010 designation dependency and original route authority, review compatible catalog cells for the added alternatives and distinguish stationary behavior from statutory standing/parking without a fabricated threshold. Build canonical semantic stages, exact selected-case Native construction, primary and three distinct risk fallbacks where required, synchronized four-camera capture, source-bound saved finalization, positive/negative compatibility, and independent delivery and comparison audits. Run the scoped strict gate before any ready label. Original motion and camera pixels require later source review; physical and legal outcomes remain unknown.
