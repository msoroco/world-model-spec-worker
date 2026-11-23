# C178244 / NRS 484B.413(2) signal-distance handoff

Status: **partial**. The CPU signal measurement and independent comparison audit are implemented and tested. The selected business-district **right-turn** branch is not delivered by this package: frozen cell C178244 is `paved_road / left_turn / other_vehicle`, and all six frozen accepted memberships are authored **left-turn** cases. Do not relabel that cell or treat the accepted metadata as right-turn proof. C378304 is a separately allocated `business_district / right_turn / freight_loading_zone` cell; any binding/coverage repair is lead-owned and must preserve the frozen inputs.

## Exact source review and scope

The full NRS 484B.413(2) requires continuous signaling over at least 100 feet traveled in a business or residential district, or 300 feet elsewhere, before a right turn, left turn, or other course change, regardless of weather. District classification is a sourced legal-context fact. Commanded activation distance is not measured distance. A legal judgment is not made here.

`case-plan.json` preserves the six existing accepted IDs and records their metadata limitations. The three historical left-turn comparisons pair business continuous/short, residential continuous/short, and other-area continuous/short. Their original traces/videos are absent from the export, so no signal distance, weather, onset, district frontage, comparison isolation, or camera visibility is established. The exact selected right-turn branch remains unresolved. No new recording is proposed solely from accepted membership.

## Implemented CPU work

`signal_distance.py` accepts an original 20 Hz Native-shaped packet with sealed result and frame-map hashes, per-frame position and actual vehicle-light readback, an independently sourced course-change onset frame, sourced district class and weather, and five on-disk source-file hash bindings. It rejects missing/stale source files, packet values that differ from source files, frame/time gaps, controller commands substituted for readback, missing onset illumination, unknown district class, and changed fixed comparison conditions. It reports observed continuous path length in feet and the statutory distance reference separately, without a legal verdict. The CLI verifies a packet before measuring or comparing it:

`.venv-cpu/bin/python work/testing__C178244__NRS-484B-413-2__motor_vehicle_driver/signal_distance.py --packet PACKET.json --source-root SAVED_SOURCE_ROOT`

For a comparison add `--compare OTHER_PACKET.json`. The source files must come from the sealed original Native capture, not from an authored target or synthetic fixture. Tests use synthetic 20 Hz packets only to prove software behavior. They include below/at/above 100-foot and 300-foot physical measurements and both turn directions.

## Proofs and status

- `.venv-cpu/bin/python runtime.py preflight`: passed with pinned CPU runtime and Lean toolchain.
- `.venv-cpu/bin/python -m unittest discover -s work/testing__C178244__NRS-484B-413-2__motor_vehicle_driver/tests -v`: 16 passed; retained in `cpu-tests.log`, with SHA256 in `result.json`.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C178244__NRS-484B-413-2__motor_vehicle_driver --complete`: passed; `static-check.log`.
- `.venv-cpu/bin/python worker_check.py --assignment testing__C178244__NRS-484B-413-2__motor_vehicle_driver --complete --require-delivery-ready`: exit 1, `strict-check.log`, because the truthful result remains partial.

Next CPU work: resolve the selected right-turn/cell mismatch through source-backed lead binding review; construct a valid right-turn exact-case package on a compatible frozen cell, including original-source capture, semantic proposals, execution manifest, exact offline and positive/negative compatibility receipts, saved-only finalization, delivery audit, and comparison audit. For the six historical left-turn members, source-review actual sealed traces if supplied; do not infer their distance or coverage from metadata. Remaining physical checks after a complete CPU package are actual motion, signal visibility, district frontage, four-camera coverage, and full-duration video decode.
