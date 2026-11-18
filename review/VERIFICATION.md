# Review verification

- Source snapshot `SOURCE-MANIFEST.json` SHA-256: `d8558406a9fe69874a5d73c97f192d47b163eee88f697b751a86bc64872572be`. Its inventoried files verified exactly.
- Exported Python suite: 224 tests ran, all passed; 10 optional/integration tests skipped. The targeted fixture and manifest suite ran 30 tests with one skip. Judgment coverage unit tests: 5 passed.
- The staged current Core decoder built successfully using Lean 4.28.0 and `build_validator`; no CARLA server was run.
- A local-only cutover rehearsal succeeded for this batch. CPU preflight passed and every frozen-file hash matched after rebinding. The demo rehearsal also proved that the exact obsolete untracked generated manifest is quarantined before replacement.
- New runtime manifest hash after rehearsal: `5b4738624542c97f321a302bd49b9ec154cb2cf63778acf64ba6042f8d5b4fd3`.
- 253 assigned; stale ready and blocked labels become partial for reassessment under the refreshed runtime.

These checks validate runtime packaging and cutover. Existing exact-case, fallback, saved-processing and comparison receipts must be rerun because they bind the previous runtime. No Native capture, physical acceptance, or complete strict worker return is claimed.
