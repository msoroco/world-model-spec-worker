# Scenario worker: full-train

## Start or resume

```sh
git clone --branch worker/full-train-delivery --single-branch https://github.com/msoroco/world-model-spec-worker.git scenario-worker-full-train
cd scenario-worker-full-train
scripts/run-worker.sh
```

For an existing checkout, stop the agent and checkpoint timer, preserve local work, pull the branch update, then run the same script. The timer pushes work; it does not pull runtime changes. Read AGENT_PROMPT.md for priorities and RUNTIME_REFRESH.md for this update.

The worker chooses serial execution or subagents according to completed-package throughput. Finished packages are published as they pass their assignment gate.
