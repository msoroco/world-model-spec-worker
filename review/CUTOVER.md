# Review-only cutover for held-out-delivery

Parent active head at preparation: `75c6b2f0e46e70df0f478ba27c470edc7220158a`. This review branch is not an agent execution branch. Do not merge or apply while the remote agent or checkpoint timer is running.

After the remote worker is stopped and all its checkpoints are pushed, fetch its final head. Merge this review branch into that final delivery head (it contains multiple commits), resolve only reviewed conflicts, and run `python3.11 review/apply.py` from the clean delivery branch. The script verifies the old and staged source hashes, replaces the old runtime without retaining its code, refreshes frozen hashes, moves ready statuses to partial because proofs changed, and preserves assignment IDs and selected cases. Commit the cutover before restarting workers. Test preflight and one exact case, then run `scripts/run-worker.sh` from a fresh clone. No force-push.

Source snapshot SHA-256: `d8558406a9fe69874a5d73c97f192d47b163eee88f697b751a86bc64872572be`. Exported Python suite: 224 tests ran, all passed (10 expected skips). Focused fixture and handoff tests: 30 passed, one skipped. This is a review candidate, not a claim that all packages are ready.

Out-of-scope work folders to remove after process/reference audit: `heldout__C293604__NRS-484B-250-3__motor_vehicle_driver` and `heldout__C5191__LVMC-11-18-030-B__motor_vehicle_driver`. Do not count them among the 51 assignments.

Held-out judgment-range audit cannot establish a comparison because the scope names no training counterpart. No artificial range input is attached.

Reference audit found that assigned packages mention those two IDs in case plans, diagnostic files, and the `lane_finalizer.py` cross-cell reference. Do not delete the folders mechanically while those links remain. The resumed worker must replace or remove the out-of-scope dependencies using the assigned 51-package scope, then delete the two extra folders and update `_shared` coverage/report files before the strict return gate.
