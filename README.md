# Scenario worker

This branch contains frozen law–cell assignment inputs. The worker prepares
runnable CARLA scenarios and CPU checks. CARLA capture and recording acceptance
happen later in the local pipeline.

## Start or resume

On a machine with Git, Codex, Python 3.11, and FFmpeg installed:

```sh
git clone --branch worker/full-test-delivery --single-branch \
  https://github.com/msoroco/world-model-spec-worker.git scenario-worker
cd scenario-worker
scripts/run-worker.sh
```

The launcher starts Codex with [START_HERE.md](START_HERE.md) as its instructions.
The agent sets up its CPU environment and works through `batch.json`. An
independent timer commits and pushes `work/` progress every 15 minutes and
after Codex exits. Run the same script again to resume; pull the branch first
if another checkout has published newer work.

Do not edit `batch.json`, `inputs/`, `partitions/`, or `runtime/`. They contain
the exact reviewed assignment context and pinned processing code. The worker
writes implementation and proof files under `work/<assignment-id>/`.

An initial assignment export has no accepted scenarios or CARLA recordings.
