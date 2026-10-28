# Reasonable-speed capability sweep

The exported batch_pipeline.sweeps.expand_sweeps froze four speed commands, 5–20 m/s at 5 m/s spacing, with clear weather and adjacent-lane traffic held fixed. These are physical coverage targets; “reasonable or proper” remains unresolved and no expected judgment labels are assigned. The baseline is unselected.

The runner authors the paved two-lane 500m road, controls the ego and traffic vehicle through native VehicleControl, records every original tick using supplied PipelineCapture, retains full bodies/weather/control and four lossless FFV1 source views. Exact offline commands and hashes are in result.json. A later operator may use `runtime.py capture` against an owned endpoint, then `analyze.py --attempt PATH --output REPORT`; it measures realized speed over native x=100..300m, traffic speed, completion, and a same-setting follow-up decision. Saved conversion/rendering use shared runtime process/render.

Physical road surface, achieved speed, traffic motion, visibility, duration, source completeness, and decoded videos remain unverified. Public-highway status is an explicit synthetic assumption. No CARLA run or physical acceptance occurred.

The analysis checks every original trace, evidence, channel and camera frame/time join, and uses supplied worker_exchange.media.audit receipts bound to source and mapping SHA. 413(2) also computes the right-lamp pixel ROI during that same source decode. Final composed video validation remains a separate downstream check.
