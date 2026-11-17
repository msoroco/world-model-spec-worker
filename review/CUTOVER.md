# Review-only cutover for full-train-delivery

Parent active head at preparation: `cc82f8a0abe413e9515e5cf5930a13fbd0e395da`. This review branch is not an agent execution branch. Do not merge or apply while the remote agent or checkpoint timer is running.

After the remote worker is stopped and all its checkpoints are pushed, fetch its final head. Rebase or cherry-pick this review commit onto that final delivery head, resolve only reviewed conflicts, and run `python3.11 review/apply.py` from the clean delivery branch. The script verifies the old and staged source hashes, replaces the old runtime without retaining its code, refreshes frozen hashes, moves ready statuses to partial because proofs changed, and preserves assignment IDs and selected cases. Commit the cutover before restarting workers. Test preflight and one exact case, then run `scripts/run-worker.sh` from a fresh clone. No force-push.

Source snapshot SHA-256: `d8558406a9fe69874a5d73c97f192d47b163eee88f697b751a86bc64872572be`. Exported Python suite: 224 tests ran, all passed (10 expected skips). Focused fixture and handoff tests: 30 passed, one skipped. This is a review candidate, not a claim that all packages are ready.

Full-train status cutover: previously blocked CPU work is downgraded to partial for reassessment under the new runtime. A worker may restore blocked only with a verified external dependency. This changes no assigned cases or underlying proof files.
