# testing__C135087__NRS-484B-153-3__motor_vehicle_driver

Status: ready for local Native delivery. Exact scoped CPU strict gate passed on 2026-11-26.

Exact law: NRS 484B.153(3), door closest to passing traffic during immediate passenger or cargo loading or unloading. The package keeps legal necessity and immediacy unresolved for human review. It does not assert that a CPU fixture demonstrates physical Native success.

Five selected cases cover active and inactive cargo and passenger loading, plus an opposite-side control. Four source-controlled comparisons isolate door side and loading activity. `case-plan.json` and `measurement-contract.json` bind the original source packets and measured geometry, articulation, loading activity, passing body and path, frame times, and four cameras.

`native_capture.py` gates a 900-frame, 20 Hz Native capture on reviewed survey and operator hashes and checks actual blueprint identities, door articulation, loading contact/motion, passing path, camera callbacks, and restoration. `native_output_bridge.py` projects the restored capture into saved traces, evidence, four FFV1 views, and a capture seal. The semantic proposals are validated for all five selected cases and their fallback candidates.

Current-hash CPU proofs passed for ten primary/fallback offline constructions, ten positive and negative compatibility checks, five saved-only processing checks, five physical/lifecycle fixture checks, five positive and negative independent delivery audits, and four positive and negative source comparison audits. Local unit discovery passed 17 tests. The exact command `.venv-cpu/bin/python worker_check.py --assignment testing__C135087__NRS-484B-153-3__motor_vehicle_driver --complete --require-delivery-ready` exited 0 with `static_checks_passed: true`.

Execution manifest SHA-256: `2a6d468a93921a61aadf78e52d50b67ac3602131d37690542f17c34eb38fed40`.
GPU queue proposal SHA-256: `648c07829475e733d716ef2cb31041c3aee4f5b84c1c3ca280ff87a6405acfc3`.
Queue proposal: `gpu-queue-proposal.json`. Original Native site, operator, articulation, loading and four-view pixels, independent physical acceptance, and legal judgment remain for local delivery/review.
