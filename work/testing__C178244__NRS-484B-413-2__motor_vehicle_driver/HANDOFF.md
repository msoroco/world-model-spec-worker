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

## 2026-11-24 original frame-map join checkpoint

The source-bound signal measurement now decodes the sealed original frame-map file and requires every frame ID and elapsed time to equal the corresponding measured signal/position sample. A recomputed frame-map digest cannot hide an altered time row. Both 100-foot and 300-foot physical boundary probes remain in the focused suite; the selected business right-turn/cell mismatch and incomplete delivery package remain unresolved CPU work.

### Receipts

- `cpu-frame-map-join-tests.log` exit 0, SHA256 `94ee1d847b701c4e11a4ee957d522df9a553037d1d1c1486cc226d6579ff3ffd`
- `cpu-frame-map-join-preflight.log` exit 0, SHA256 `74bc4630e0b05dc75d95d65c41b53f9f77312576d1bd2c0275026da5f3a660b6`
- `cpu-frame-map-join-static.log` exit 0, SHA256 `f0d9b4c1febf22e3df2ea98e277eb6dd5767c1433d5b35d13f070446a8e33aec`
- `cpu-frame-map-join-strict.log` exit 1, SHA256 `3dbf09ddc86f7b16bc918693f7addafe40dc0e1599312455aaf56edb7f7a180a`
- `signal_distance.py` SHA256 `1c9152dd0d1bd8513fb980c25dd88e86248672faa2696919f247ae6da9015048`
- `tests/test_signal_distance.py` SHA256 `598155976e9aa64ece55fade2c9d93dc4bbdc3705bc1492739790c93e6d22a71`

Seventeen focused tests, pinned preflight and scoped complete static check pass. Exact scoped strict exits 1 because status remains partial. Next CPU work: source-backed exact right-turn construction and full canonical compatibility/delivery proof, preserving the frozen left-turn cell and accepted metadata.

## 2026-11-25 original turn-direction binding

`signal_distance.py` now requires original sealed-result case identity and turn direction, plus independently observed turn-onset direction, to match the measurement packet. It rejects a left-turn packet relabeled right even if the sealed-result file is rehashed. Eighteen focused tests pass in `cpu-source-direction-tests.log`.

The exact alternate-cell prerequisite is lead/shared binding reconciliation: frozen `inputs/.../assignment.json` fixes C178244 to `left_turn`, while its selected branch is business-district right-turn. `inputs/coverage/candidate-cells.json` lists C378304 as `business_district/right_turn`; `work/testing__C378304__NRS-484B-413-2__motor_vehicle_driver/result.json` already reports a ready CPU package for this selected branch with five exact cases and three comparisons. FULL_BRANCH_CONTRACT requires an additional binding for incompatible fixed maneuvers. C178244 may retain its six historical left-turn metadata cases, but they are not right-turn evidence. The scoped strict gate must remain partial until the lead resolves this binding without modifying the frozen cell or asserting unsupported existing-evidence coverage.

Scoped static check passes in `cpu-nov25-static.log`; exact strict check exits 1 in `cpu-nov25-strict.log` with `Preparation acceptance failed: partial/missing packages remain`.
## 2026-11-26 environment rerun and immutable branch review

The updated pinned CPU environment passes `runtime.py preflight` and all 18 signal-distance tests. The tests establish source-file hash checks, frame joins, turn-direction binding, sampled 100/300-foot measurements, and comparison context rejection; they do not replace absent original Native traces/videos. Exact scoped strict still exits 1 at the truthful partial status. Receipts and hashes are in `result.json`.

The exact frozen C178244 catalog cell fixes `paved_road / left_turn / other_vehicle`. Its only selected branch in `inputs/.../assignment.json` is business-district right-turn signaling. All six accepted memberships and three historical comparisons in this package are left-turn; their accepted metadata contains no original signal readback, turn-onset or district proof. Constructing right-turn evidence here would contradict the fixed cell. `FULL_BRANCH_CONTRACT.md` section 29 calls for an additional compatible binding when fixed maneuver is incompatible. C378304 is a separately allocated `business_district / right_turn / freight_loading_zone` assignment and its CPU package is ready, so the remaining step for this selected branch is lead-owned shared binding reconciliation. No legal/physical outcome is claimed for the six historical left turns, and their source-bound measurement procedure remains available if original records become present.
## 2026-11-26 source-bound accepted-recording reprocessing

`accepted_source.py` admits original trace and video bytes for each of the six frozen C178244 accepted memberships only if exact case/law/cell/actor/status and both SHA256 values match frozen metadata, the frozen evidence inventory and acceptance bindings. `review_accepted.py` then joins a sourced signal packet to that admission, checks the left-turn identity, district class encoded by the accepted case, declared 900-frame duration, all five independent source-file hashes, observed light readback and course-change onset, and reports physical signal distance. It does not infer an original result from metadata or decide statutory compliance. The six frozen original trace and video paths were checked on this worker host and none is present. A local operator can run the source admission and review when those exact archived bytes are available.

The focused suite now passes 30 tests, including altered trace/video bytes, a different actor/case, missing media, right-turn substitution, district substitution, and existing frame/time/source/distance tests. All scratch directories used by the suite are under `.runtime-work/`. `review_accepted_comparison.py` now supplies that independent source-bound fixed-condition review for all three historical districts, including a measured distance difference and rejection of changed route; execution on actual original packets remains pending because the media is absent. This reprocessing path preserves accepted evidence and does not propose duplicate recording merely because the exported media is absent. The selected business right-turn branch remains on the compatible C378304 batch assignment, subject to lead-owned coverage reconciliation. C178244 is still partial; no original or physical claim is made.
## 2026-11-27 selected right-turn allocation audit

`right_turn_binding_audit.py` seals the two frozen assignments, candidate-cell catalog, batch, and current C378304 plan, selected manifest and readiness result. `right-turn-binding-audit.json` proves the C178244 fixed maneuver is left turn while its assigned branch text names a business-district right turn. C378304 has the compatible fixed business-district/right-turn cell and CPU-ready selected cases `short80`, `continuous100`, `above101`, `interrupted` and `rain`; its three comparisons cover the 100-foot physical boundary, continuity and weather. The audit rejects stale target readiness and a missing 100-foot selected case. It does not claim an original C378304 recording or legal outcome. C178244's six accepted left-turn metadata records remain distinct and cannot be relabeled as right turns.

All 33 C178244 CPU tests passed in `cpu-nov27-binding-tests.log`, including the existing accepted-original source admission, signal-distance frame/source checks, independent accepted comparisons and three allocation tests. Runtime preflight passed in `cpu-nov27-binding-preflight.log`; the scoped static gate passed in `cpu-nov27-binding-static.log`. The exact scoped strict gate exited 1 in `cpu-nov27-binding-strict.log` because `result.json` truthfully remains partial. Original trace/video bytes for the six accepted left-turn memberships remain unavailable in this export; their existing source-bound reviewer can process them if supplied. The selected right-turn branch is CPU-prepared in C378304 but cannot be claimed under C178244's immutable left-turn cell.

Resume by reconciling the frozen branch/cell allocation while retaining C378304's right-turn identity and this assignment's left-turn historical evidence review. If a valid left-turn statutory branch is allocated to C178244, select exact source-gated left-turn constructions and proofs under that corrected branch, then rerun `.venv-cpu/bin/python worker_check.py --assignment testing__C178244__NRS-484B-413-2__motor_vehicle_driver --complete --require-delivery-ready`. Do not dispatch a C178244 right-turn job or mark this package ready solely from the C378304 CPU package.

| November 27 file | SHA256 |
| --- | --- |
| `right_turn_binding_audit.py` | `a49ffa6d7c4a5bf6c62132e6a7c4313ea314c6d022abf112bd24c18b06efd037` |
| `right-turn-binding-audit.json` | `bde18ff5acae9166c3059717b115f0c9b10079e248ef39d48a9ad65bb2b82210` |
| `tests/test_right_turn_binding_audit.py` | `6f8c24d3250f87dd4efc67235b06614e2e8b27b59d2624bdc2c8fb1555b30fad` |
| `cpu-nov27-binding-tests.log` | `5203145b2a9fba836f9aca23c52e97267ddfac9e77ed8c62521d27fb5c301a59` |
| `cpu-nov27-binding-preflight.log` | `98572f4c859224804281754dd7ccb2fea67faad4b23eff15eb9c5d66d7b9cdf5` |
| `cpu-nov27-binding-static.log` | `f0d9b4c1febf22e3df2ea98e277eb6dd5767c1433d5b35d13f070446a8e33aec` |
| `cpu-nov27-binding-strict.log` | `0d28089dee3f920ecd20a6ba1cea1530562eeb871c292d0f8a76c869d4230638` |

## November 27 fixed-input contradiction sealed

Status remains **partial**. Frozen `assignment.json` (SHA-256 `d016fa0e3e1bb665756b4270d0ba9f3495e35bf6a0a3c95bd0a2a7acaa14f6f4`) binds the sole selected branch “Business-district right-turn signaling” to exact cell C178244, whose immutable maneuver is `left_turn`. The frozen witness (SHA-256 `2191c7fcbac8d085604511bedea750824e3c4c48eed6bcaf19e5b6149d5b23f2`) and candidate catalog (SHA-256 `d067de719af99bb6b0bf1c0cf513f64df3f63e5e8f340d8339650770b711798a`) distinguish the compatible C378304 `business_district/right_turn` cell. `FULL_BRANCH_CONTRACT.md` (SHA-256 `248028f36ba8fcfde214182376a4d049804be6da1472940ddfb72e5552c4ce36`, fixed-maneuver allocation paragraph) requires a separate compatible binding for an incompatible fixed maneuver.

The current source-hashed allocation audit passes (`cpu-nov27-fixed-binding-audit.log`, SHA-256 `bde18ff5acae9166c3059717b115f0c9b10079e248ef39d48a9ad65bb2b82210`), verifying the separate C378304 assignment (SHA-256 `587ffe4fae90daaaafa083cf75342ee439ca301b1d2ab24d9f498a21660ddc6f`) and its CPU-ready selected manifest/result (SHA-256 `fdfe45b0d3b05bc3ce9d70f7850ea62e117103ddd9df093d0723cc539aa2770e` / `6caf004e1cc00e0c9916318dda8ea1a20d70b75b8c7e13fc2a08a7613fd8cfae`). All 33 local tests pass (`cpu-nov27-fixed-binding-tests.log`, SHA-256 `c971d3d20fe584ab55d204865bf058ab3a75b1d1e214c21a194eb8f480282d24`), and the scoped `--complete` check passes (`cpu-nov27-fixed-binding-static.log`, SHA-256 `f0d9b4c1febf22e3df2ea98e277eb6dd5767c1433d5b35d13f070446a8e33aec`). These CPU checks do not relabel six left-turn accepted metadata rows or prove their absent original traces/videos.

Resume action: reconcile the frozen branch/cell allocation through the authorized coverage process. Keep the business right-turn selected work with compatible C378304; allocate a genuine left-turn branch to C178244 if that work is intended. Original source review remains necessary for any physical or legal outcome.

## November 27 current runtime proof and reconciliation action

The pinned runtime preflight passed (`cpu-nov27b-preflight.log`, SHA-256 `b33a0b4764ff18b696d6b966be9597a168bc0671f198d9221714e55582b3f185`). All 33 source-bound CPU tests passed (`cpu-nov27b-tests.log`, SHA-256 `936977cdbf7147221014f30139b3212777e3cf0f521e440bf001ffcc80edbc48`). The source-hashed alternate-cell audit passed (`cpu-nov27b-binding.log`, SHA-256 `bde18ff5acae9166c3059717b115f0c9b10079e248ef39d48a9ad65bb2b82210`). The scoped `--complete` check passed (`cpu-nov27b-static.log`, SHA-256 `f0d9b4c1febf22e3df2ea98e277eb6dd5767c1433d5b35d13f070446a8e33aec`). The exact scoped strict command exited 1 (`cpu-nov27b-strict.log`, SHA-256 `0d28089dee3f920ecd20a6ba1cea1530562eeb871c292d0f8a76c869d4230638`) because `result.json` remains partial.

All six original `acceptance.trace_source` and `acceptance.video_source` absolute paths in the frozen accepted metadata are absent on this worker host. Their metadata cannot establish measured turn direction, signal distance, or camera coverage. The `accepted_source.py` and `review_accepted.py` admission path remains available if the exact archived bytes and associated source packet are provided; it does not turn a left-turn recording into a right-turn case.

The next CPU delivery step requires an authorized branch/cell allocation consistent with the fixed maneuver. The selected business-district right-turn comparison is already CPU-prepared on compatible C378304. A genuine C178244 left-turn assignment would permit this owner to build selected left-turn constructions and proof receipts; without that allocation, a C178244 right-turn construction would contradict the frozen cell. Preserve this package as partial and rerun the exact scoped strict command after any authorized allocation update.

## November 27 final scoped CPU and source reconciliation

The current pinned runtime preflight, all 33 focused source-bound tests, the separate compatible-cell binding audit, and the assignment-scoped complete check passed. The exact assignment-scoped strict gate exited 1 solely because this result remains truthfully partial; its log is retained below. The source review was repeated against all six frozen accepted metadata records: every original trace and video path remains absent, so the historical left-turn memberships cannot establish actual signal distance, original turn direction, or the selected right-turn outcome. The frozen selected branch/cell contradiction cannot be repaired inside this returned package without changing the assignment’s immutable identity or representing a left turn as a right turn. No source-backed right-turn construction for C178244 is permissible under its fixed left-turn maneuver.

The authorized resume input is a corrected branch/cell allocation that places business right-turn on the already prepared compatible C378304 assignment and, if intended, allocates a left-turn branch to C178244. Then construct and prove exact C178244 selected cases for that corrected scope. Until then this package remains partial.

| Current receipt | Exit | SHA256 |
| --- | ---: | --- |
| `cpu-nov27-final-preflight.log` | 0 | `b9fea8700c72d1d20657fd867beb294669e74b80cc73461e1121090c23a94a63` |
| `cpu-nov27-final-tests.log` | 0 | `7abc7cd72823e83929b040e7fd0a910be269d3ab0f8dd51331e2113b5292f7f2` |
| `cpu-nov27-final-binding.log` | 0 | `bde18ff5acae9166c3059717b115f0c9b10079e248ef39d48a9ad65bb2b82210` |
| `cpu-nov27-final-static.log` | 0 | `f0d9b4c1febf22e3df2ea98e277eb6dd5767c1433d5b35d13f070446a8e33aec` |
| `cpu-nov27-final-strict.log` | 1 | `0d28089dee3f920ecd20a6ba1cea1530562eeb871c292d0f8a76c869d4230638` |

## November 27 accepted-packet custody repair

Independent review found that `review_accepted.py` admitted frozen trace and video hashes but previously measured a separate signal packet whose own hash was not joined to the frozen accepted evidence inventory. `accepted_source.verify_packet_binding` now requires the exact packet path and SHA-256 in that recording's frozen `evidence.json` source list before signal measurements or comparisons run. It also rejects a packet outside the frozen evidence root. The reviewer records the admitted packet hash. Its five referenced source files are still checked for byte hashes and observation joins by `signal_distance.py`.

The current six frozen accepted rows list metadata but no original signal packets; their original trace/video bytes are also absent. Accordingly this repair prevents a substitute packet from being presented as an accepted original measurement. Synthetic fixtures with a source-listed packet prove the positive code path; new negative tests reject a changed packet and a missing frozen packet entry. The full focused suite passed 35/35, pinned runtime verification and preflight passed, and the scoped `--complete` check passed. The exact scoped strict gate still exited 1 because the selected business right-turn branch conflicts with the fixed C178244 left-turn cell and the result remains partial. No original signal distance, right-turn case or legal outcome is claimed.

| Current file | SHA-256 |
| --- | --- |
| `accepted_source.py` | `ce94b3433b5b30e0bb9d2bcb1df76fce8a3bbd64cfef14b2cafac8a9e34f7607` |
| `review_accepted.py` | `4a4797ef75612041f0923d42a3eaa21d4ff4b4c902cbb916f7def497903a2ad1` |
| `tests/test_review_accepted.py` | `3094f2a78afc25aea388c84b62dedac53b4f65829fc3fb565f431b8bac0ed12b` |
| `cpu-nov27-packet-binding-tests.log` | `0f8484d0dca36efa10d9daacb3a954fa9bdc80b0a4b50ca31906fa8435933319` |
| `cpu-nov27-packet-binding-static.log` | `f0d9b4c1febf22e3df2ea98e277eb6dd5767c1433d5b35d13f070446a8e33aec` |
| `cpu-nov27-packet-binding-strict.log` | `0d28089dee3f920ecd20a6ba1cea1530562eeb871c292d0f8a76c869d4230638` |
| `result.json` | `fe82add6f81b653db6282f969e86b8e455d5274c11139de089fbd4880eba1c3b` |

Resume the historical left-turn review only when original trace, video and an independently frozen signal packet source are present, and correct the selected branch/cell allocation before any C178244 delivery-ready claim. The compatible business right-turn package remains C378304.

## November 27 selected-branch allocation seal

The C178244-to-C378304 allocation audit now verifies that both frozen assignments name the exact selected business-district right-turn branch. It already checked the frozen left-turn versus right-turn maneuvers, compatible target district and actor, all five target selected manifest cases, three controlled comparisons, and the target's CPU-ready result. Two new negative tests reject changed selected branches in either frozen assignment. The full local suite passed 37/37; the audit and scoped `--complete` check passed. The exact scoped strict check exited 1 because C178244 correctly remains partial. No original accepted signal measurement or C178244 right-turn delivery is claimed.

| Current receipt | Exit | SHA256 |
| --- | ---: | --- |
| `cpu-nov27c-tests.log` | 0 | `8edbaf70d375e3a42552a5568850011f451cc68050637c35fe8b1db0e106ff78` |
| `cpu-nov27c-audit.log` | 0 | `7c168f093eb2e3c311b3af0368ccccc2d744d3e9bf914bcc5e663123e526e081` |
| `cpu-nov27c-static.log` | 0 | `f0d9b4c1febf22e3df2ea98e277eb6dd5767c1433d5b35d13f070446a8e33aec` |
| `cpu-nov27c-strict.log` | 1 | `0d28089dee3f920ecd20a6ba1cea1530562eeb871c292d0f8a76c869d4230638` |

The remaining preparation decision is the frozen branch/cell contradiction. Correct the allocation through the authorized source process; preserve C378304 for the selected right-turn branch. If C178244 is assigned a left-turn branch, author its selected construction and exact proofs from that corrected scope. The six historical accepted rows still require their original source bytes and a frozen packet entry before source-bound measurement.

## November 27 accepted-source and success-ledger review

Six evidence-review facts in `case-plan.json` now cite only the exact accepted recording metadata source in the frozen evidence inventory. Their demonstrated facts are limited to what that metadata establishes; the separately hashed review context remains a planning source, not accepted observation proof. `branch_coverage.validate_evidence` passed and its one-line receipt is `cpu-nov27-evidence-binding.log` (SHA-256 `a25bef30db26b744c82cd26de0d77f4fd5393014f342af4b2880b080bf0bae83`). Original trace, video and signal packet remain absent.

The result success ledger now excludes six historical strict-failure diagnostic logs; those files remain under this assignment. Its 37-test suite and scoped `--complete` passed. The exact scoped strict command still exits 1 at truthful partial status. A read-only virtual-ready diagnostic reaches `Missing requirement dispositions`: the selected business right-turn requirement cannot truthfully be assigned to this frozen left-turn cell. Preserve the C378304 compatible right-turn package; resume C178244 selected construction only after the authorized branch/cell allocation is corrected and original sources are available.

## November 27 original-recording join proof

`signal_distance.verify_source_bindings` now requires the original trace and video SHA-256 values in both the frozen signal packet and its sealed result source. `review_accepted.review` joins those values to the exact admitted recording's frozen trace and video hashes before reporting a signal measurement. The measurement receipt carries both hashes. Two new CPU tests reject a packet rebound to different original bytes and a packet whose hash fields disagree with its sealed result; the missing-source test also covers both original hash fields. This tightens the historical accepted-evidence review without selecting those left-turn records for the assigned right-turn branch.

With `SCENARIO_PIPELINE_OUTPUT_ROOT` under `.runtime-work/` and bytecode writes disabled, the assignment suite passed 39/39. `cpu-nov27-original-join-tests.log` has SHA-256 `d6c3e4f7c656b71b49b4f41f776cdd6cb60831f6c202a70a1b90be3c3f6e263b`. The current right-turn allocation audit was rerun against current target sources; `right-turn-binding-audit.json` has SHA-256 `7c168f093eb2e3c311b3af0368ccccc2d744d3e9bf914bcc5e663123e526e081`. All 29 success-ledger receipt hashes now match their files. The scoped static check passed. Original trace/video and a frozen signal packet are still absent from this export, and the left-turn/right-turn allocation remains unresolved; status stays partial.

## November 27 Core timeline join

The accepted-recording reviewer now parses the admitted original Core `trace.json`, requires the complete declared scene count and increasing integer millisecond timestamps, and joins every signal packet sample frame/time to the corresponding Core scene timestamp. Its receipt reports scene count, first/last timestamp and joined sample count. This matches the pinned local acceptance timeline convention while remaining a structural check: it does not derive light state, turn onset, position or video visibility from the Core trace. Those observations remain dependent on the separately frozen packet and independent source review.

Two new negative tests reseal fixture metadata and packet hashes around incomplete or changed Core traces, then confirm the reviewer rejects the original scene history or timestamp join after admission. The full assignment suite passed 41/41 with output under `.runtime-work/`; `cpu-nov27-original-join-tests.log` has SHA-256 `c30f45bf532f228c0d7bef34098c10b5916bbc360e3beb46c0d467af3320ed71`. All 29 result success-ledger hashes match, scoped `--complete` passed, and the exact strict command still exits 1 at truthful partial status. Original trace/video and signal packet are absent from the export; the selected right-turn versus frozen left-turn allocation remains unresolved.

## November 27 nonzero Native timestamp support

The original-frame signal-distance measurement now uses the first observed frame timestamp as the 20 Hz time origin. The pinned Native frame map permits a nonzero first time; requiring frame zero at `0.0 s` could reject a valid admitted recording. The Core timeline join still compares each packet time with its exact original scene millisecond timestamp. Tests now use an admitted 900-scene Core trace beginning at `50 ms`, exercise a `0.05 s` packet start, and reject an altered frame interval or invalid first time. This change preserves observed distance and signal logic and does not infer legal compliance.

The full assignment suite passed 43/43. `cpu-nov27-original-join-tests.log` has current SHA-256 `461f906a1958d584d7db6bfe4c4336bde29b5ebb342a9e18d460bc93979bf371`; all 29 success-ledger receipts match. Scoped `--complete` passed. The exact strict check still exits 1 at truthful partial status. The original accepted source bytes and frozen signal packet are absent, and the selected business right-turn branch still conflicts with the frozen C178244 left-turn cell.

## November 27 admitted Core indicator cross-check

The accepted-recording reviewer now compares each packet signal sample with the admitted original Core scene's subject `sig.turn_indicator` when that observed field exists. It requires a unique subject user for each checked scene, rejects malformed signal data and rejects any lamp-state disagreement. The finding reports `core_indicator_samples_checked`; fixture records with no Core indicator explicitly report zero. This check does not invent observations for the six historical accepted recordings whose original trace/video and frozen signal packets are absent from this export.

The full assignment suite passed 45/45, including a positive indicator join and a sealed-source conflict rejection. `cpu-nov27-original-join-tests.log` has SHA-256 `7522f23e2c879b0fc89efb1f0b481af7d06c22a767e4939a94d435289a8f2d64`. All 29 result success-ledger receipts match their files, and scoped `--complete` passed. The exact scoped strict check still exits 1 because status remains truthful partial. The selected business right-turn branch still conflicts with frozen C178244 left-turn control, and no original source or GPU queue entry was promoted.

## November 27 original position type proof

`signal_distance.measure` now rejects Boolean Native x/y positions and non-object sample rows. Python otherwise treats `True` as an integer, which could turn an invalid original transform into a distance sample. Two CPU tests exercise both rejection paths. The full assignment suite passed 47/47; `cpu-nov27-original-join-tests.log` has SHA-256 `ffebf7fe6fc3d8286c567954ac9f45b19ed768e7cd587f5d43f7a5a87b1b5227`. All 29 result success-ledger hashes match their files. Pinned runtime verify/preflight and scoped `--complete` passed. The exact scoped strict command still exits 1 on truthful partial status. The frozen C178244 left-turn cell remains inconsistent with its selected business right-turn branch; original accepted trace/video and signal packet remain absent, so no source-bound physical outcome or GPU-ready promotion is claimed.

## November 27 original frame identity proof

`signal_distance.measure` now requires actual integer frame IDs and turn-onset index, excluding Boolean values that Python would otherwise treat as integers. The new CPU test rejects a Boolean frame 1 and Boolean turn onset. The full assignment suite passed 48/48 and scoped `--complete` passed. Exact `--require-delivery-ready` still exits 1 on truthful partial status: C178244 is frozen left-turn while its selected branch is right-turn, and the original accepted trace/video/signal packets are absent. No physical outcome or selected right-turn delivery is claimed.

Test receipt: `cpu-nov27d-tests.log` SHA256 `d24612b3cda9a26d52f453e61b63b2099a03da6757e5a11b872be999ad93b189`; static receipt: `cpu-nov27d-static.log` SHA256 `f0d9b4c1febf22e3df2ea98e277eb6dd5767c1433d5b35d13f070446a8e33aec`.
