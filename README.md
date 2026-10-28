# Portable scenario preparation

Read START_HERE.md. This repository supplies the main pipeline runtime, law inputs, worked examples, and four demo-test partitions (22 assignments: 6/6/5/5). No upstream repository, database, GPU, NERSC tools or simulator is required for preparation. The operator manually starts the agent.

Implementation goes in work/<assignment-id>/. inputs/ and runtime/ are frozen sources. Existing migration-candidates are untrusted references, not accepted packages. Physical motion, visibility, adequate duration and recording acceptance require later local verification.

Follow UPDATE.md and numbered notices at safe checkpoints. Only the lead merges main, commits and pushes the batch return branch; do not force-push. See MIGRATION.md for setup, shared interfaces, readiness and takeover.
