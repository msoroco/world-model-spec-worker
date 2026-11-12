"""Independent source and saved-processing audit for the finite listener sweep."""
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FIXED = ('ego_turn_motion.jsonl', 'ego_signal_audio.jsonl', 'turn_originals.jsonl',
         'listener_audio_original.jsonl', 'horn_actuation.jsonl', 'affected_participants.json',
         'trace.jsonl', 'video_frames.jsonl')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def audit(folder=HERE, source_override=None):
    folder = Path(folder)
    packets = []
    for offset in (2, 4, 6):
        prefix = f'listener-{offset}m'
        case = folder.name + f'__ped_horn_listener_{offset}m'
        recipe = json.loads((folder / f'{prefix}-recipe.json').read_text())
        source = ROOT / recipe['generator']['source']
        require(sha(source) == recipe['generator']['sha256'], 'Stale listener diagnostic source')
        diagnostic = json.loads(source.read_text())
        files = dict(diagnostic['files'])
        if source_override and offset in source_override:
            files.update(source_override[offset])
        require(json.loads(files['turn_fixture_provenance.json'])['case_id'] == case,
                'Wrong listener case provenance')
        motion = [json.loads(line) for line in files['ego_turn_motion.jsonl'].splitlines()]
        bodies = [json.loads(line) for line in files['participant_bodies.jsonl'].splitlines()]
        require(len(motion) == len(bodies) and len(motion) > 0,
                'Missing original listener body frames')
        gaps = []
        for ego, row in zip(motion, bodies):
            require(ego['frame'] == row['frame'], 'Misjoined listener body frame')
            listener = row['bodies']['ped_listener']
            require(listener['x_m'] == 0 and listener['y_m'] == offset,
                    'Listener diagnostic point differs from selected offset')
            gap = math.hypot(ego['x_m'] - listener['x_m'], ego['y_m'] - listener['y_m'])
            gap -= ego['body_radius_m'] + listener['body_radius_m']
            require(math.isfinite(gap), 'Nonfinite listener body gap')
            gaps.append(gap)
        manifest = json.loads((folder / f'{prefix}-manifest.json').read_text())
        entry = manifest['cases'][0]
        construction = folder / entry['construction']
        receipt_path = folder / f'{prefix}-saved-receipt.json'
        receipt = json.loads(receipt_path.read_text())
        require(entry['case_id'] == case and sha(construction) == entry['construction_sha256'],
                'Listener exact construction differs')
        require(receipt['case_id'] == case and receipt['passed'] is True and
                receipt['originals_preserved'] is True and receipt['missing_evidence'] is False and
                receipt['native_revision']['construction_sha256'] == entry['construction_sha256'],
                'Listener saved processing differs')
        for name in (*FIXED, 'participant_bodies.jsonl'):
            require(receipt['original_source_hashes'].get(name) ==
                    hashlib.sha256(files[name].encode()).hexdigest(),
                    'Listener saved original source differs: ' + name)
        packets.append({'case_id': case, 'offset_m': offset, 'minimum_sampled_ped_gap_m': min(gaps),
                        'source_sha256': sha(source), 'construction_sha256': sha(construction),
                        'saved_receipt_sha256': sha(receipt_path),
                        'fixed_source_sha256': {name: hashlib.sha256(files[name].encode()).hexdigest()
                                                for name in FIXED}})
    require(all(packet['fixed_source_sha256'] == packets[0]['fixed_source_sha256']
                for packet in packets[1:]), 'Fixed original turn, signal or audio source differs')
    return {'format': 'worker-listener-distance-sweep-audit', 'points': packets,
            'diagnostic_fixture': True, 'physical_audibility_verified': False,
            'affected_party_judgment_verified': False, 'legal_acceptance_claimed': False}


if __name__ == '__main__':
    result = audit()
    (HERE / 'listener-sweep-audit.json').write_text(json.dumps(result, indent=2) + '\n')
    print('listener_sweep_source_and_saved_audit_passed', len(result['points']))
