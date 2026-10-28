# Continuation infrastructure (update 003)

These editable helpers are shared by the existing partition packages. Supplied runtime sources remain frozen; worker_exchange/common.py and runtime_contract.py are exact local copies for standalone bundles.

- contracts.py: strict recorded-output checks using the supplied runtime contract. Checks measured targets and causal evidence, non-null mandatory channels, matching original timestamps/rates, decodable encoded-video frame counts, context, participant histories, footprint histories and recomputable measurement windows. Passing synthetic fixtures establishes software behavior only.
- recording.py: tick-neutral PipelineCapture integration, four camera queues and VP9/WebM encoders, original trace/frame joins, mandatory measured channels and independent cleanup callbacks. Runtime requires CARLA, supplied runtime/python dependencies, ffmpeg with libvpx-vp9 and ffprobe. The local installed FFmpeg lacks libx264 and mpeg4; actual VP9 fixtures pass.
- materialize.py: checks inline shared source content, writes complete case bundles into temporary repository directories, and runs offline --check plus assignment unit tests in those materialized directories. It does not connect to CARLA.

Run shared tests: `python3.11 -m unittest discover -s work/_shared/tests`.
Run all bundles: `python3.11 work/_shared/materialize.py --all`.
Run submission validation: `python3.11 worker_check.py --complete`.
Run preparation acceptance separately: `python3.11 worker_check.py --require-ready`.

A partial result is a checkpoint. Structured external requirements must name requirement, category (implementation, live_measurement or external_asset), evidence, next_action and requires_live_execution. An unimplemented channel, encoder, feature or check remains implementation work. Runtime acceptance never copies requested targets into observations or derives legal judgment standards from engineering tolerances.
