"""Build a reference candidate that derives mandatory channels in saved processing."""
import argparse
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
MANIFEST = HERE / 'execution-manifest.json'
EXTRA = ('ego_speed', 'newly_laid_footprint_contact',
         'drive_over_warned_new_pavement')


def build(candidate='primary'):
    if candidate not in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        raise ValueError('Unknown reference candidate')
    source = HERE / 'draft-measured-candidates/reference' / candidate / 'construction.json'
    target = HERE / 'draft-integrated-reference' / candidate / 'construction.json'
    draft_manifest = HERE / ('update152-draft-integrated-manifest.json' if candidate == 'primary'
                             else f'update152-draft-integrated-{candidate}-manifest.json')
    construction = json.loads(source.read_text())
    files = {item['path']: item for item in construction['files']}
    contract = files['native/recording_contract.py']['content']
    contract = contract.replace(
        "'pavement_footprint_contact')",
        "'pavement_footprint_contact',\n            'ego_speed', 'newly_laid_footprint_contact',\n            'drive_over_warned_new_pavement')")
    if contract == files['native/recording_contract.py']['content']:
        raise ValueError('Recording contract insertion point changed')
    files['native/recording_contract.py']['content'] = contract
    files['native/recording_contract.py'].pop('source', None)

    finalizer = files['native/finalize.py']['content']
    finalizer = finalizer.replace(
        'from recording_contract import CHANNELS, ASSIGNMENT, description',
        'from recording_contract import CHANNELS, ASSIGNMENT, description\n'
        'from mandatory_channels import derive as derive_mandatory_channels')
    finalizer = finalizer.replace(
        "streams = {name: (folder/(name+'.jsonl')).open('x') for name in CHANNELS}",
        "streams = {name: (folder/(name+'.jsonl')).open('x') for name in CHANNELS[:4]}")
    finalizer = finalizer.replace(
        "    context = attempt/'recorded-context.json'",
        "    mandatory_folder = attempt/'mandatory-derived'\n"
        "    derive_mandatory_channels(attempt, mandatory_folder)\n"
        "    for name in CHANNELS[4:]:\n"
        "        (mandatory_folder/(name+'.jsonl')).replace(folder/(name+'.jsonl'))\n"
        "    context = attempt/'recorded-context.json'")
    for token in ('from mandatory_channels import derive', 'CHANNELS[:4]',
                  'derive_mandatory_channels(attempt, mandatory_folder)'):
        if token not in finalizer:
            raise ValueError('Finalizer insertion failed: ' + token)
    files['native/finalize.py']['content'] = finalizer
    files['native/finalize.py'].pop('source', None)
    construction['files'].append({
        'path': 'native/mandatory_channels.py',
        'content': (HERE/'derive_mandatory_channels.py').read_text(),
        'source': str((HERE/'derive_mandatory_channels.py').relative_to(HERE.parents[1])),
    })

    namespace = {}
    exec(compile(contract, 'recording_contract.py', 'exec'), namespace)
    description = namespace['description'](600)
    construction['recording_description'] = description
    config = json.loads(files['config.json']['content'])
    config['recording_description'] = description
    files['config.json']['content'] = json.dumps(config, indent=2, sort_keys=True) + '\n'
    construction['status'] = 'partial'
    construction['delivery_ready'] = False
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(construction, indent=2, sort_keys=True) + '\n')

    manifest = json.loads(MANIFEST.read_text())
    reference = next(item for item in manifest['cases']
                     if item['case_id'] == HERE.name + '__reference')
    selected = reference if candidate == 'primary' else next(
        item for item in reference['candidates'] if item['id'] == candidate)
    selected['construction'] = str(target.relative_to(HERE))
    selected['construction_sha256'] = hashlib.sha256(target.read_bytes()).hexdigest()
    reference['candidate_offline_status'] = 'pending'
    selected['compatibility'] = None
    selected['offline'] = None
    if candidate == 'primary':
        reference['post_capture'] = None
    draft_manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'construction': str(target),
                      'sha256': selected['construction_sha256'],
                      'manifest': str(draft_manifest)}, sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--candidate', default='primary')
    build(parser.parse_args().candidate)
