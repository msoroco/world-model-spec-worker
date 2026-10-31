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
`model_reasoning_effort=medium`. The worker needs Git push access. Automatic
approval may still reject a push; the prompt requires preserving the local
commit and reporting that rejection.


## Notes
### Progress checkpoints

The lead agent commits and attempts to push coherent work during the run,
using `scripts/checkpoint.sh "short progress summary"` after every eight
completed assignment packages or at least every 30 minutes when files have
changed, whichever happens first. The script stages only `work/`, leaves
frozen inputs alone, and retries an earlier unpushed commit. Assignment
subagents never commit or push. A failed checkpoint push must not stop
independent preparation; the lead records the failure and continues.
