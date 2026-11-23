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


def collect(complete):
    manifest = json.loads(MANIFEST.read_text())
    rows = []
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        folder = PACKAGE / 'diagnostic-fixture' / suffix
        for candidate in [{'id': 'primary', 'construction': entry['construction'],
                           'construction_sha256': entry['construction_sha256']},
                          *entry['candidates']]:
            ident = candidate['id']
            positive = folder / ('attempt-' + ident + '-profile.log')
            saved = folder / ('saved-' + ident + '-profile.log')
            if not positive.is_file() or not saved.is_file() or not positive.stat().st_size or not saved.stat().st_size:
                if complete:
                    raise ValueError('Missing current diagnostic receipt: ' + suffix + '/' + ident)
                continue
            compatibility = json.loads(positive.read_text())
            processing = json.loads(saved.read_text())
            if not compatibility['passed'] or not processing['passed'] or not processing['recorded_only']:
                raise ValueError('Diagnostic CPU proof failed: ' + suffix + '/' + ident)
            if (compatibility['case_id'] != entry['case_id'] or
                processing['case_id'] != entry['case_id'] or
                compatibility['candidate_id'] != ident or processing['candidate_id'] != ident or
                compatibility['construction_sha256'] != candidate['construction_sha256'] or
                sha(PACKAGE / candidate['construction']) != candidate['construction_sha256'] or
                compatibility['negative_removed'] != 'reviewed-curb.json' or
                not compatibility['negative_log_sha256']):
                raise ValueError('Diagnostic binding mismatch: ' + suffix + '/' + ident)
            proof_dir = folder / 'proofs'
            proof_dir.mkdir(exist_ok=True)
            shutil.copyfile(positive, proof_dir / ('profile-' + ident + '-positive.json'))
            shutil.copyfile(saved, proof_dir / ('profile-' + ident + '-saved.json'))
            rows.append({'case_id': entry['case_id'], 'candidate_id': ident,
                         'construction_sha256': candidate['construction_sha256'],
                         'compatibility_receipt_sha256': sha(positive),
                         'saved_receipt_sha256': sha(saved),
                         'fixture_recipe_sha256': sha(ROOT / entry['fixture_recipe'])})
    if complete and len(rows) != 12:
        raise ValueError('Expected all twelve diagnostic candidate chains')
    checkpoint = {'format': 'c229398-current-profile-checkpoint-v1',
                  'manifest_sha256': sha(MANIFEST), 'candidate_chains_passed': len(rows),
                  'complete': len(rows) == 12, 'diagnostic_only': True,
                  'delivery_selected': False, 'original_native_observed': False,
                  'candidates': rows}
    output = PACKAGE / 'diagnostic-fixture' / 'profile-checkpoint.json'
    output.write_text(json.dumps(checkpoint, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'candidate_chains_passed': len(rows),
                      'manifest_sha256': checkpoint['manifest_sha256'],
                      'checkpoint_sha256': sha(output)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--complete', action='store_true')
    collect(parser.parse_args().complete)
