# Exact comparison audit

The crest pair uses `crest` and `feature` as labels for the same physical controller interval. The audit compares each phase's first frame, last frame, and target speed, while checking the intended lane-target difference separately. This keeps timing and speed fixed without treating a label as physical evidence.

`crest-left-side-selftest.log` records the positive source-bound comparison and two negative mutations. A one-frame timing change and a 1 m/s speed change each raise `Fixed controller phase schedule differs`.
