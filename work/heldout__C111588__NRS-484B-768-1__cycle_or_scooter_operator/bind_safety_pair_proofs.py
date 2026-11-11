"""Retain exact offline, compatibility and saved proof sources for the safety pair."""
from hashlib import sha256
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PREFIX = 'heldout__C111588__NRS-484B-768-1__cycle_or_scooter_operator__'
CASES = [('safety_wide', 'wide', 'f', 'h'), ('safety_narrow', 'narrow', 'c', 'c')]


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def copied(source, target):
    shutil.copy2(source, target)
    return {'file': target.name, 'sha256': digest(target)}


for slug, short, offline_revision, compat_revision in CASES:
    folder = ROOT / 'cases' / slug
    offline = REPO / '.runtime-work' / f'c111588-safety-{short}-offline-{offline_revision}'
    compat = REPO / '.runtime-work' / f'c111588-safety-{short}-compat-{compat_revision}'
    saved = REPO / '.runtime-work' / f'c111588-safety-{short}-saved-c/v0001'
    receipt = json.loads((compat / 'compatibility.json').read_text())
    processing = json.loads((saved / 'processing.json').read_text())
    manifest = ROOT / f'safety-{short}-manifest.json'
    construction = folder / 'construction.json'
    assert receipt['passed'] and receipt['construction_sha256'] == digest(construction)
    assert receipt['case_id'] == PREFIX + slug and receipt['negative_removed'] == 'participant_motion.jsonl'
    assert processing['passed'] and processing['originals_preserved'] and not processing['missing_evidence']
    assert processing['native_revision']['construction_sha256'] == digest(construction)
    assert not processing['physical_acceptance_claimed'] and not processing['legal_acceptance_claimed']
    files = {}
    for label, source in {
        'offline_log': offline / 'offline.log',
        'compatibility_receipt': compat / 'compatibility.json',
        'compatibility_analysis_log': compat / 'compatibility-analysis.log',
        'compatibility_negative_log': compat / 'negative-analysis.log',
        'saved_receipt': saved / 'processing.json',
        'saved_analysis_log': saved / 'analysis.log',
    }.items():
        files[label] = copied(source, folder / ('proof-' + label.replace('_', '-') + source.suffix))
    observed = receipt['measurement_examples']['rider_clearance_observation']['value']
    proof = {'format': 'worker-rider-safety-pair-proof', 'case_id': PREFIX + slug,
             'construction_sha256': digest(construction),
             'manifest_sha256': digest(manifest),
             'measurement_contract_sha256': digest(folder / 'measurement-contract.json'),
             'fixture_recipe_sha256': digest(folder / 'diagnostic-recipe.json'),
             'files': files, 'offline_passed': True, 'compatibility_passed': True,
             'missing_original_negative_passed': True, 'saved_processing_passed': True,
             'originals_preserved': True,
             'minimum_center_distance_m': observed['minimum_center_distance_m'],
             'time_to_conflict_s': observed['time_to_conflict_s'],
             'physical_participant_visibility_verified': False,
             'legal_safety_judgment': None, 'diagnostic_fixture_only': True}
    (folder / 'proof.json').write_text(json.dumps(proof, indent=2, allow_nan=False) + '\n')
    print(slug, proof['minimum_center_distance_m'], 'offline/compatibility/saved passed')
