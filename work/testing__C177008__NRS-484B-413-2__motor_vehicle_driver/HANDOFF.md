# C177008 NRS 484B.413(2) delivery handoff

Status: ready for original source review and GPU delivery. Exact scoped CPU strict gate passed on 2026-11-26; this is a prepared package, not an accepted physical capture.

The frozen assignment targets business-district right-turn signaling for motor_vehicle_driver in C177008 (`paved_road/change_lane/other_vehicle`). The plan retains the source cell identity and requires a reviewed physical right turn, sourced district/frontage classification, sourced other vehicle and driver/vehicle, an actual signal controller, and 20 Hz synchronized four-view Native capture. The two frozen accepted recordings are reviewed at metadata level only and do not establish law-specific original coverage. The accepted-evidence fact bindings cite only frozen accepted metadata; the separate review context remains background.

Five selected cases cover sufficient 35 m business signaling, short 20 m business signaling, an interruption in a 35 m approach, a 35 m other-area contrast, and rain invariance. Four pairwise comparisons isolate lead distance, continuity, district threshold and weather. The legal references remain exactly 100 ft (30.48 m) and 300 ft (91.44 m); case distances are engineering requests. The selected Native handoff has source gates before CARLA import and original 20 Hz frame/time/pixel/signal checks. Fallback1 adds a second sampled controller lead for onset drift, with physical risk retained.

CPU proofs: 20 unit tests; five primary and five fallback offline checks; ten positive/negative compatibility receipts; five recorded-only saved processing receipts; five physical preparation/lifecycle receipts; five independent diagnostic delivery positive/negative receipts for both `demo-test` and `full-test`; and four saved-source comparison receipts with stale-source rejection. The semantic index has five selected stages. The exact scoped `worker_check.py --assignment testing__C177008__NRS-484B-413-2__motor_vehicle_driver --complete --require-delivery-ready` exited 0 and reported `static_checks_passed: true`.

The queue proposal is `gpu-queue-proposal.json`. First GPU dispatch is `result.json.first_gpu_delivery_command`. Before any physical delivery, obtain and review the original right-turn site/route, business or other-area district facts, other-vehicle blueprint and spawn, signal-controller capability, original camera visibility and all original physical outcome evidence. Do not substitute the diagnostic fixtures for those sources. Independent local acceptance remains after capture.

| File | SHA256 |
| --- | --- |
| `case-plan.json` | `6a5e3f2ecf36e8d874aa8e810afbe4da491e1609f150f73cc9ea483d2147f288` |
| `execution-manifest.json` | `4f710a64a93ca1a16ae6a5be4ad940cbd22dfb10f2812bd3d8d706126702c93b` |
| `gpu-queue-proposal.json` | `11325aa65ad9a1ee4d80d344b3e38fdef29ab9df6780554e131e3b5623283ece` |
| `result.json` | `24d9a11c56af0b0a69baae92d94a5bcd1ac2a429f08543bd6ed203fd05205a2a` |
| `unittest.log` | `962778bafc98f8572ee748384c246d8d6444dbcb2bcd903204719688d9524945` |
| `strict-ready.log` | `f8c181254d86e6c1ce23cb72cb518b6dcbd394fe00c463d27bf232e0f63fdb54` |
| `delivery-audit-receipts.json` | `38eca86d06ce9c4db6499128dcc245a7067d5dc7aec4ae97d9ecdfce17d5dbd6` |
| `comparison-audit-receipts.json` | `30d6f2ddb99b1501294807f3da776b8cdf9d865fd7685625475d362e764867d8` |
| `saved-processing-receipts.json` | `6c4e5a9fb5b83d11f5963fad9bf98029fc4b6fa3558c47b4e1b19db23d0f0a5d` |

## Exact saved-processing repair, 2026-11-27

The five exact manifest cases now carry executable recorded-only `process-saved` commands and matching failure-feedback commands. `prove_post_capture.py` exercised each command on its source-shaped compatibility attempt using a diagnostic owner-release receipt. All five processed successfully with preserved originals, passing final-video checks; all five missing-validator runs failed with actionable `feedback.json` and no Native replay. These software receipts do not assert original physical or legal acceptance.

The bound `cpu-nov27-post-saved-all.log` SHA256 is `d639f04144df7b85709a56466ca5f5146b223993fceb963a028f838cf529f9b0`. The exact scoped `worker_check.py --assignment testing__C177008__NRS-484B-413-2__motor_vehicle_driver --complete --require-delivery-ready` exited 0; `strict-post-capture.log` reports `static_checks_passed: true`. Current manifest SHA256 is `4f710a64a93ca1a16ae6a5be4ad940cbd22dfb10f2812bd3d8d706126702c93b`.
