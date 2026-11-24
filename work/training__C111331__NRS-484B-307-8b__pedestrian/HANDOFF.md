# training__C111331__NRS-484B-307-8b__pedestrian

Status: **partial CPU implementation checkpoint**. No case is selected for delivery. No original governing signal, pedestrian crossing, alternate-device permission, or legal outcome is claimed.

## Statutory scope and current proof

The exact law concerns pedestrians facing a steady red signal alone: they shall not enter the highway unless another device permits proceeding under NRS 484B.283. The current planned comparison varies highway entry while holding the authored facing-red signal and absence of another permitting device fixed. The conditional other-device exception is a separate unfinished branch. The frozen local selection snapshot lists no accepted membership row; no historical recording is claimed reusable.

`native/red_entry.py` authors two synthetic 600-frame, 20 Hz, 30-second pedestrian footprint traces. Condition A stays outside the highway; condition B enters during the steady-red interval. The context specifies a signal head, facing vector and pedestrian approach vector; their dot product is checked, but Native governing authority is explicitly unverified. `prove-red-entry-source.py` measured the source pair and rejected six damaged-source/authority variants, including wrong head, changed color, spurious other-device permission and opposite facing. `native/build_runtime_offline.py` binds the frozen law and source hashes into two unselected draft constructions. Both pass the current pinned `runtime.py offline` runner under `.runtime-work/c111331/offline-a` and `offline-b`. `audit-red-entry-current.py` independently checked all 1,200 source rows, footprint entry, fixed signal/exception context, and construction hashes. Proof and log hashes are in `result.json`. The assignment-scoped complete check passed; the strict variant failed on this partial package.

## Remaining CPU work

Implement actual Native pedestrian motion and establish that the specific steady-red head governs and faces this pedestrian, with four synchronized source-camera streams and decoded pixels. Separately construct and prove the NRS 484B.283 alternate-device permission branch rather than treating its absence in this diagnostic pair as coverage. Build source-derived public compatibility and actual process-saved positive/negative checks, physical-risk candidates, semantic proposals, and independent delivery/comparison audits. Do not infer legal compliance from the synthetic entry contrast. Keep status partial until the assignment-scoped strict gate passes.
