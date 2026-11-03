# Full-train worker batch

Fresh portable CPU preparation checkout for the frozen `full-train` scope. It contains eight assignment partitions, exact law/cell inputs, one source-hashed runtime, small examples and no campaign database or canonical recordings. Start with [AGENT_PROMPT.md](AGENT_PROMPT.md).

Selected CARLA cases are delivery cases. GPU execution and recording acceptance occur later in the main pipeline. This branch contains no earlier trial returns or versioned runtime copies.

## Start the agent

On the machine that will run the worker agent:

```bash
git clone --branch worker/full-train-delivery --single-branch \
  https://github.com/msoroco/world-model-spec-worker.git scenario-worker-full-train
cd scenario-worker-full-train
scripts/run-worker.sh
```

The launcher uses **GPT-6-sol with medium reasoning**. To use GPT-6.1-sol,
run `WORKER_CODEX_MODEL=gpt-6.1-sol WORKER_CODEX_REASONING=low scripts/run-worker.sh`
instead. It checks Git identity and attempts a dry-run push before spending
model time. A later push can still fail; the timer logs and retries it.

## Keep the long task active

If you use an interactive Codex session, set this Goal in that same session
before giving the agent the task:

```text
/goal Complete the full-train-delivery work in AGENT_PROMPT.md. Continue through all independent assignments and finish with either a passing strict delivery gate or a best-effort return that identifies every unresolved blocker. Preserve frozen inputs and truthful readiness statuses.
```

Then prompt: `Read AGENT_PROMPT.md and complete the work assigned in batch.json. Do not edit batch.json. Do not commit or push; the separate timer publishes Git checkpoints.`
The launcher requests Goal creation in its ordinary prompt;
it does not run `/goal` as a shell or CLI command. Goal support depends on the
Codex build. A Goal helps maintain the objective across turns. It does not
restart a stopped agent.


## Notes
### Progress checkpoints

`scripts/run-worker.sh` starts a separate Git timer before Codex. Every
15 minutes it commits changed files under `work/` and attempts to push the
branch. No changed files means no new commit. Failures are recorded under
ignored `.runtime-work/worker-run.*/checkpoint.log` and retried on later
ticks. After Codex finishes, the timer makes one more attempt at its next
scheduled tick, within 15 minutes, and stops. No Git command is triggered by
the exit itself. The launcher reports a failed final checkpoint. Set
`WORKER_CHECKPOINT_INTERVAL_SECONDS` to change the interval.
