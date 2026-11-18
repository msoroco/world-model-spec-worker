# Review-only cutover for demo-test-delivery

Parent active head at preparation: `18934f5a175862c2db0c02fc5dde69b0a8be1cec`. This review branch is not an agent execution branch. Do not merge or apply while the remote agent or checkpoint timer is running.

After the remote worker is stopped and all its checkpoints are pushed, fetch its final head. Merge this review branch into that final delivery head (it contains multiple commits), resolve only reviewed conflicts, and run `python3.11 review/apply.py` from the clean delivery branch. The script verifies the old and staged source hashes, replaces the old runtime without retaining its code, refreshes frozen hashes, moves ready statuses to partial because proofs changed, and preserves assignment IDs and selected cases. Commit the cutover before restarting workers. Test preflight and one exact case, then run `scripts/run-worker.sh` from a fresh clone. No force-push.

Source snapshot SHA-256: `d8558406a9fe69874a5d73c97f192d47b163eee88f697b751a86bc64872572be`. Exported Python suite: 224 tests ran, all passed (10 expected skips). Focused fixture and handoff tests: 30 passed, one skipped. This is a review candidate, not a claim that all packages are ready.

Demo-test judgment report SHA-256: `ce8a03d9574c66cafb1470c681bc6e9ac41007a5eaf9eff64abfb2220b4e2f3b`. Its `passed` field is false with 14 historical gaps; preserve those limitations.
