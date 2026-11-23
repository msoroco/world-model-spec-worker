"""Bind current diagnostic compatibility and saved receipts to draft inputs."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent.parent
ROOT = PACKAGE.parents[1]
MANIFEST = PACKAGE / 'draft-primary-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def collect(complete, tag):
    manifest = json.loads(MANIFEST.read_text())
    rows = []
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        folder = PACKAGE / 'diagnostic-fixture' / suffix
        for candidate in [{'id': 'primary', 'construction': entry['construction'],
                           'construction_sha256': entry['construction_sha256']},
                          *entry['candidates']]:
            ident = candidate['id']
            positive = folder / ('attempt-' + ident + '-' + tag + '.log')
            saved = folder / ('saved-' + ident + '-' + tag + '.log')
            if not positive.is_file() or not saved.is_file() or not positive.stat().st_size or not saved.stat().st_size:
                if complete:
                    raise ValueError('Missing current diagnostic receipt: ' + suffix + '/' + ident)
                continue
            compatibility = json.loads(positive.read_text())
            processing = json.loads(saved.read_text())
            construction = json.loads((PACKAGE / candidate['construction']).read_text())
            config = json.loads(next(item['content'] for item in construction['files']
                                     if item['path'] == 'config.json'))
            cameras = config['cameras']
            if [(camera['name'], camera['width'], camera['height']) for camera in cameras] != [
                ('overview', 1920, 1080), ('approach', 1280, 720),
                ('reference_corner', 1280, 720), ('driver_reference', 1280, 720)]:
                raise ValueError('Camera dimensions differ: ' + suffix + '/' + ident)
            if any(camera.get('pose_strategy') != 'ego_attached_fixed_offset' or
                   camera.get('fov_deg') != 90 for camera in cameras):
                raise ValueError('Camera strategy differs: ' + suffix + '/' + ident)
            if tag == 'atoms' and config.get('required_atoms') != [
                    'kin.extent', 'rel.occupies', 'kin.position']:
                raise ValueError('Pinned Core atom selection differs: ' + suffix + '/' + ident)
            if not compatibility['passed'] or not processing['passed'] or not processing['recorded_only']:
                raise ValueError('Diagnostic CPU proof failed: ' + suffix + '/' + ident)
            if (compatibility['case_id'] != entry['case_id'] or
                processing['case_id'] != entry['case_id'] or
                compatibility['candidate_id'] != ident or processing['candidate_id'] != ident or
                compatibility['construction_sha256'] != candidate['construction_sha256'] or
                sha(PACKAGE / candidate['construction']) != candidate['construction_sha256'] or
                compatibility['runtime_manifest_sha256'] != manifest['runtime_manifest_sha256'] or
                compatibility['fixture_recipe_sha256'] != sha(ROOT / entry['fixture_recipe']) or
                compatibility['negative_removed'] != 'reviewed-curb.json' or
                not compatibility['negative_log_sha256'] or
                not processing['originals_preserved']):
                raise ValueError('Diagnostic binding mismatch: ' + suffix + '/' + ident)
            proof_dir = folder / 'proofs'
            proof_dir.mkdir(exist_ok=True)
            shutil.copyfile(positive, proof_dir / (tag + '-' + ident + '-positive.json'))
            shutil.copyfile(saved, proof_dir / (tag + '-' + ident + '-saved.json'))
            feet = {'below_15_ft': 14, 'at_15_ft': 15, 'above_15_ft': 16}[suffix]
            attempt = ROOT / '.runtime-work' / (
                'c229398-compat-' + str(feet) + 'ft-' + tag + '-' + ident)
            for source_name, target_name, expected in (
                ('compatibility-analysis.log', tag + '-' + ident + '-analysis.log',
                 compatibility['log_sha256']),
                ('negative-analysis.log', tag + '-' + ident + '-negative-analysis.log',
                 compatibility['negative_log_sha256'])):
                source = attempt / source_name
                if sha(source) != expected:
                    raise ValueError('Missing or changed compatibility log: ' + suffix + '/' + ident)
                shutil.copyfile(source, proof_dir / target_name)
            rows.append({'case_id': entry['case_id'], 'candidate_id': ident,
                         'construction_sha256': candidate['construction_sha256'],
                         'compatibility_receipt_sha256': sha(positive),
                         'saved_receipt_sha256': sha(saved),
                         'fixture_recipe_sha256': sha(ROOT / entry['fixture_recipe'])})
    if complete and len(rows) != 12:
        raise ValueError('Expected all twelve diagnostic candidate chains')
    checkpoint = {'format': 'c229398-current-' + tag + '-checkpoint-v1',
                  'manifest_sha256': sha(MANIFEST), 'candidate_chains_passed': len(rows),
                  'complete': len(rows) == 12, 'diagnostic_only': True,
                  'delivery_selected': False, 'original_native_observed': False,
                  'candidates': rows}
    output = PACKAGE / 'diagnostic-fixture' / (tag + '-checkpoint.json')
    output.write_text(json.dumps(checkpoint, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'candidate_chains_passed': len(rows),
                      'manifest_sha256': checkpoint['manifest_sha256'],
                      'checkpoint_sha256': sha(output)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--complete', action='store_true')
    parser.add_argument('--tag', choices=('profile', 'camera', 'atoms'), default='profile')
    args = parser.parse_args()
    collect(args.complete, args.tag)
