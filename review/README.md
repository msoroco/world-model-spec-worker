# full-train-delivery worker

After the reviewed cutover is applied on `worker/full-train-delivery`, start from a fresh clone and run:

```sh
scripts/run-worker.sh
```

The agent resumes the exact assignments and existing work in this branch. It prepares CPU delivery packages and publishes checkpoints through the separate timer. It does not run CARLA or accept recordings. Read `AGENT_PROMPT.md` for the current proof contract.
