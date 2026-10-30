---
name: nersc-gpu-access
description: Inspect NERSC host access and GPU resources through read-only SSH checks, with at most six concurrent checks. Use to assess resources for a specified workload or a user-provided Slurm allocation; never request an allocation or launch a workload as part of inspection.
---

# NERSC GPU access

Check reachability and resource availability before GPU execution. This is a resource-inspection skill, separate from the six scenario-processing stages. Resource snapshots are not reservations or proof that a workload will fit.

## Inspect hosts

Confirm the current hostname and any existing Slurm allocation from the environment. Do not assume the session remains on login11. Treat login01 through login40 as candidate hostnames to verify, not forty guaranteed available GPUs. Inspect explicitly requested hosts first; inspect additional candidates when a resource search is requested. Compute hosts must come from the user's existing allocation.

Use read-only SSH with `BatchMode=yes`, `StrictHostKeyChecking=yes`, and `ConnectTimeout=10`. Bound each complete remote inspection to 30 seconds, and run no more than **six concurrent SSH checks**. Do not change SSH configuration or host-key files. Skip unreachable hosts, authentication failures, and unknown host keys, recording the reason instead of prompting or retrying indefinitely.

For each reachable host, collect hostname, GPU index/model, total and free GPU memory, GPU utilization, available host memory, CPU load, and applicable CPU/memory limits where readable. A compact GPU query is:

```bash
nvidia-smi --query-gpu=index,name,memory.total,memory.free,utilization.gpu --format=csv,noheader
```

Use read-only host and cgroup queries for effective limits; distinguish host-wide availability from the resources accessible to this user. Report unavailable metrics as unknown. Record the observation time. Occupied GPU memory matters even when utilization is zero.

## Assess suitability

Compare each snapshot against the workload's documented or previously measured GPU-memory, host-memory, and CPU requirements, including any stated headroom. Report resource insufficiency or uncertainty explicitly. If requirements or effective limits are unknown, show the available metrics without claiming that resources are sufficient. Do not invent a universal free-memory or utilization cutoff.

Recheck resources immediately before any separately authorized execution. Never stop other processes, change GPU settings, or create an allocation to free resources.

## Execution boundary

Inspection does not launch CARLA, run benchmarks, or execute other GPU workloads. Never submit Slurm jobs or request resources automatically; use an allocation the user has provided. SSH access and apparently free resources do not establish exclusive ownership.

## Report and review

Return a compact table of host, GPU, free memory, utilization, host resource limits, and suitability or missing requirements. Include observation time and inspection failures. Generate no files by default; if explicitly asked to save a pipeline report, place it in the applicable cell/law workspace, or its campaign administration logs, inside the configured pipeline output root.

Before reporting, verify that failed hosts were skipped, GPU memory and effective host limits were considered, concurrency stayed at six or fewer, and no workload or allocation was started. This skill adds no human approval gate; execution remains subject to the user's authorization and supplied resources.

Follow [the storage workflow](../../docs/storage.md) for saved reports. Resource inspection does not export, consolidate, or package datasets.

Use [the workspace index](../../docs/storage.md#active-implementation-workspaces) for active implementation: `work/{demo,held-out,train,test}/<cell>/<law>/`. Full sets share their demo workspace. Use `workspaces` path helpers for campaign administration and shared semantic outputs. Historical campaign directories are recovery sources; new edits belong in indexed workspaces and require fresh frozen runtime provenance before execution.
