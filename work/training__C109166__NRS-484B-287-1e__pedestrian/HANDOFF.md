# NRS-484B-287-1e at C109166

Actor: `pedestrian`. Frozen cell: `intersection` / `enter_road` / `traffic_control_device`.

Exact source: NRS 484B.287(1)(e). The full text and source hash are retained in `case-plan.json`; extracted summary status is `recovered_requires_source_review`. Witness branch: Authorized crossing initiated by road entry.

Controlled variable: `device state during diagonal crossing`. Requested pair: cross diagonally under the governing diagonal-cross permission; cross diagonally against the governing diagonal-cross device. These are construction requests, not measurements or legal verdicts. The baseline is unselected.

Statutory branch dispositions: 2. Review each exception and dependency against the exact text before physical selection. Accepted membership rows: 0; no source-hashed equivalence receipt is available, so reuse is unclaimed.

Blocker: No executable Native construction or four distinct candidates have been built; offline and compatibility proofs, measured-result finalization, positive/negative saved fixtures, independent audit and physical realization remain unverified.

Resume: build Native geometry, actor control, cameras and mandatory capture for each runnable branch; prepare four distinct source-preserving constructions per selected case; run exact pinned-runtime offline and compatibility checks, saved positive/negative fixtures and an independent audit. Set `ready` only after those CPU proofs pass.

Source-context review: Diagonal crossing requires independent authorization and the particular official device governing diagonal movement; ordinary crosswalk permission is insufficient.

## Current-runtime source checkpoint

`native/diagonal.py` and `prove-diagonal-source.py` construct two 600-frame, 20 Hz, 30-second synthetic diagonal-crossing source requests. The pedestrian center and four-point footprint traverse a 16.97 m diagonal from frames 100 through 340. The controlled pair keeps that route fixed; only the named governing device state changes on frames 180 through 239. The saved measurement reports zero versus 60 denied-during-crossing frames. Five malformed inputs were rejected (missing frame, off-route center/footprint disagreement, wrong device identity, missing full body, and non-governing context). These are timing and source-integrity measurements, not observed simulation or legal conclusions. Original official-device pixels and diagonal authorization remain unreviewed.

Reproduction: `PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/training__C109166__NRS-484B-287-1e__pedestrian/prove-diagonal-source.py`. Proof SHA-256: `90d421816fe153f82bc80ac40f609c443f027c0c52ce3bb2e9ebdc89130e142b`. Module SHA-256: `e65fbe2ab0d17e84e067bb6be673f098c68722024db8f6eda70581e511f6f4bb`. Proof runner SHA-256: `e74bda29cbf0c793f1419683f6e52959e4104113e87ae95a0e36178e9b848b6f`.

Current-runtime CPU preflight passed (`current-preflight.log`, SHA-256 `5929cfc751f06630ee9c7966b7a90a9c6e5ffab5ed7995b42a7efda2cf60ab3e`). Assignment-scoped `worker_check.py --assignment training__C109166__NRS-484B-287-1e__pedestrian --complete` passed static checks. Package remains `partial`; the strict delivery check was not run because no ready claim is made. Next owner must turn the source request into an executable Native intersection with a demonstrably official diagonal head and independent authorization source, capture four cameras for at least 30 seconds, produce four candidates per selected case, and run Core/Lean/render/final-decode, saved fixture and independent audit proofs before any ready status.
