# One-way direction capability

The two exact nonbaseline cases use the same two-lane eastbound road and authored OneWay signal. One native controller follows the designated eastbound direction; the other drives westbound along the same physical right-side lane, retaining full original body, heading, control, sign inventory, and four lossless source views. The baseline is unselected. Public-way status and designation are explicit synthetic assumptions.

Run each exact offline command in result.json. A later operator may use `runtime.py capture` against an already-owned CARLA endpoint, then `analyze.py --attempt PATH --output REPORT`. This measures actual travel direction, full-body roadway occupancy, and native sign inventory; rendered sign visibility and its governed extent still need saved-source review. Shared PipelineCapture, process, and render supply capture/conversion/video processing. No CARLA episode or physical acceptance occurred.

The analysis checks every original trace, evidence, channel and camera frame/time join, and uses supplied worker_exchange.media.audit receipts bound to source and mapping SHA. 413(2) also computes the right-lamp pixel ROI during that same source decode. Final composed video validation remains a separate downstream check.
