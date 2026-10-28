# Portable scenario preparation

This Git repository carries four demo-test partitions, 22 frozen law/cell
assignments, the pinned main-pipeline runtime and Core library, examples, and
the worker acceptance check. Read [START_HERE.md](START_HERE.md) to start a
fresh preparation trial. The operator launches the agent manually.

Implementation belongs in `work/<assignment-id>/`. Inputs and runtime are
frozen. The worker prepares and tests cases without CARLA, a campaign database,
or NERSC. Local GPU execution and physical acceptance happen later.
