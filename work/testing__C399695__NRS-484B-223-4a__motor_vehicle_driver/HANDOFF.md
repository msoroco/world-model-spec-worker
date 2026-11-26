# C399695 NRS 484B.223(4)(a) handoff

Status: ready for original Native GPU acquisition; exact scoped CPU strict gate passed. Frozen assignment SHA256 `4a9e941fc83d5b446b4f5a640e01051e65c45d4029e34c2ba479d65316db8440`. No accepted original recording exists yet.

Four exact delivery cases distinguish independently sourced right-turn, through, and left-turn purpose from observed departure route. The right-turn route mismatch case preserves right-turn purpose while requesting a separately sourced alternate exit. Two controlled comparisons cover declared purpose and purpose-route agreement. Purpose is never inferred from lane occupancy or a completed turn.

Source-gated `right_turn.py` and `original_runner.py` require a reviewed public highway, single exclusive right-turn lane, connected T-junction exit, separate purpose declaration before lane entry, Native spawn pose and trajectory. `right_turn_carla_adapter.py` and `right_turn_capture.py` specify 900 original 20 Hz frames and four synchronized cameras. `analysis.py` recomputes saved-only lane and route measurements from the original packets. Physical and pixel acceptance remains for GPU capture and independent review.

Selected and source-bound fallback bundles passed pinned offline and positive/negative compatibility checks for all four cases, including actual saved analysis, Lean Core and four-camera full decode diagnostics. Physical, lifecycle and independent delivery CPU proofs passed for all four. Both comparison audits pass positive diagnostic fixtures and reject a changed fixed map. These synthetic diagnostics make no claim of real physical completion or legal verdict.

Exact command: `.venv-cpu/bin/python worker_check.py --assignment testing__C399695__NRS-484B-223-4a__motor_vehicle_driver --complete --require-delivery-ready` passed with exit 0. `strict.log` SHA256 `34ac2ba7b6b800e062a8ec7c1b4212b33156e3e8074a8c71db8fce655c62fa5e`. `execution-manifest.json` SHA256 `203db390a526902fc621b5299d7e0744ceeaed8eb4e2e1070f36bd49c25a3b75`. `gpu-queue-proposal.json` SHA256 `dd5246ea94b086b84e65443d4c6988933d9d4a6972ec0ca0861dea0374763a85`. `comparison-proposal.json` SHA256 `7079a5288925eaf80885de4dca15b9fcb03cf1f9c9059dd74236194be21a0e7c`.

GPU follow-up: acquire separately reviewed original Native evidence for each case; inspect actual lane and route readback, four-view pixels and physical completion; review statutory purpose application. Use the manifest candidate trigger only where original evidence shows a controller lane or exit risk. Do not treat the CPU synthetic fixtures as accepted recordings.
