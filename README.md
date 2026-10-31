# Full-train worker batch

Fresh portable CPU preparation checkout for the frozen `full-train` scope. It contains eight assignment partitions, exact law/cell inputs, one source-hashed runtime, small examples and no campaign database or canonical recordings. Start with [AGENT_PROMPT.md](AGENT_PROMPT.md).

Selected CARLA cases are delivery cases. GPU execution and recording acceptance occur later in the main pipeline. This branch contains no earlier trial returns or versioned runtime copies.

## Start the agent

On the machine that will run the worker agent:

```bash
git clone --branch worker/full-train-delivery --single-branch \
  https://github.com/msoroco/world-model-spec-worker.git scenario-worker-full-train
cd scenario-worker-full-train
codex exec --approve-for-me -s workspace-write \
  -m gpt-6-sol -c model_reasoning_effort=medium \
  "Read AGENT_PROMPT.md and complete the work assigned in batch.json. Do not edit batch.json."
```

If available, I recommend **GPT-6-sol with medium reasoning**, or
**GPT-6.1-sol with low or medium reasoning**. To use the latter, replace the
`-m` value with `gpt-6.1-sol` and set `model_reasoning_effort=low` or
`model_reasoning_effort=medium`. The worker needs Git push access.

## Keep the long task active

If you use an interactive Codex session, set this Goal in that same session
before giving the agent the task:

```text
/goal Complete the full-train-delivery work in AGENT_PROMPT.md. Continue through all independent assignments, publish progress checkpoints, and finish with either a passing strict delivery gate or a pushed best-effort return that identifies every unresolved blocker. Preserve frozen inputs and truthful readiness statuses.
```

Then prompt: `Read AGENT_PROMPT.md and complete the work assigned in batch.json. Do not edit batch.json.`
The `codex exec` command above is the one-shot launch path; `/goal` is an
interactive command, so do not paste it into the `codex exec` prompt and assume
it will be interpreted as a command. A Goal helps maintain the objective
across turns. It does not replace checkpoint pushes or restart a stopped agent.


## Notes
### Progress checkpoints

The lead agent commits and attempts to push coherent work during the run,
using `scripts/checkpoint.sh "short progress summary"` after every eight
completed assignment packages or at least every 30 minutes when files have
changed, whichever happens first. The script stages only `work/`, leaves
frozen inputs alone, and retries an earlier unpushed commit. Assignment
subagents never commit or push. A failed checkpoint push must not stop
independent preparation; the lead records the failure and continues.
