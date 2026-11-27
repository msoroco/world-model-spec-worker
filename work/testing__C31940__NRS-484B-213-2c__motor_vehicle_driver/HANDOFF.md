# NRS 484B.213(2)(c) bridge approach delivery

Status: CPU delivery prepared; original CARLA acceptance pending. Exact assignment: `testing__C31940__NRS-484B-213-2c__motor_vehicle_driver`.

Six exact cases cover the obstructed bridge approach at 101, 100 and 99 feet from the reviewed entrance, clear view, right-side travel and the one-way-highway subsection 3 exception. The 101-foot case uses root `construction.json`; five other primary constructions are under `cases/`. Each case has a concrete fallback controller, and `case-plan.json` defines five controlled comparisons. The statutory distance is measured from the reviewed bridge entrance to the ego front body edge; no engineering tolerance is treated as a legal tolerance. Original view obstruction and highway directionality require review.

The manifest `execution-manifest.json` pins each construction, offline and compatibility receipts, source-bound physical fixture/lifecycle proofs, saved-only processing, independent delivery audit and controlled comparisons. `semantic-index.json` under `proposals/` binds exact law, exception, parameters and unresolved view-obstruction judgment. `queue-proposal.json` has the six delivery rows and comparison follow-ups.

CPU checks: four focused unit tests pass. All six primary and six fallback offline/compatibility runs pass. All six saved-only runs pass. Each physical fixture/lifecycle proof passes. Delivery audits accept intact diagnostic receipts and reject missing original bridge history; five comparison audits accept the intact pair and reject altered history. These diagnostic CPU fixtures do not establish original CARLA motion or legal view obstruction.

GPU delivery must provide a reviewed source packet binding the actual public-highway bridge, entrance, centerline, highway directionality, ego body length and planned occluder. Use `result.json` `first_gpu_delivery_command` with the local runtime/DB/CARLA variables. Preserve original videos, bridge history, source hashes, Native exit, restoration and owner release; independently review pixels and the statutory view condition.
