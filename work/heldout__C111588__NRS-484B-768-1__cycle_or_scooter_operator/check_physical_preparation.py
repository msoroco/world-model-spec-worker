"""Validate the three selected rider case physical-preparation receipts."""
import json
from pathlib import Path

from worker_exchange.physical_preparation import validate

folder = Path(__file__).resolve().parent
repo = folder.parents[1]
for name in ('first-execution-manifest.json', 'no-signal-manifest.json',
             'continuous-manifest.json', 'electric-bicycle-manifest.json',
             'electric-scooter-manifest.json', 'safety-wide-manifest.json',
             'safety-narrow-manifest.json', 'turn-lane-manifest.json',
             'both-hands-manifest.json'):
    entry = json.loads((folder / name).read_text())['cases'][0]
    validate(repo, folder, entry)
print('nine physical preparation proofs pass')
