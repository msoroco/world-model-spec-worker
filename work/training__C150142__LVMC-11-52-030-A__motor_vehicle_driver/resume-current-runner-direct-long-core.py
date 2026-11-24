"""Resume an interrupted direct synthetic long Core diagnostic.

The retained positive attempt has already completed composition and finalization.
This script verifies its source identity before the Native, Core and media steps.
It is not a public fixture-recipe compatibility receipt.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys


WORK = Path(__file__).resolve().parent
REPO = WORK.parents[1]
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from batch_pipeline.carla import validate_attempt
from worker_exchange.media import audit
from worker_exchange.runtime_cli import process, render

MANIFEST = WORK / 'current-runtime-runner-reference-saved-source-manifest.json'
SOURCE = REPO / '.runtime-work/c150142-direct-long-compat-tour-bus-below-primary-current-v2/fixture'
CASE = WORK.name + '__tour_bus_below'


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def read(path):
    return json.loads(path.read_text())


def run(output, validator):
    output = Path(output).resolve()
    validator = Path(validator).resolve()
    if REPO / '.runtime-work' not in output.parents or not validator.is_file():
        raise ValueError('Use an existing ignored attempt and pinned validator')
    positive = output / 'positive'
    if not (positive / 'result.json').is_file() or not (positive / 'four-view-receipt.json').is_file():
        raise ValueError('Long finalizer and composition have not completed')
    if (positive / 'converted').exists():
        raise ValueError('Prior Core output exists; inspect it before resuming')
    manifest = read(MANIFEST)
    entry = next(item for item in manifest['cases'] if item['case_id'] == CASE)
    selection = read(positive / 'candidate-selection.json')
    if (selection['manifest_sha256'] != sha(MANIFEST) or
            selection['construction_sha256'] != entry['construction_sha256'] or
            selection['candidate_id'] != 'primary'):
        raise ValueError('Retained attempt has another candidate or manifest')
    required = ('video_frames.jsonl', 'native-raw-actors.jsonl',
                'native-passenger-actors.jsonl', 'trace.jsonl',
                'statutory-context.json', 'native-map-readback.json')
    source_hashes = {}
    for name in required:
        a, b = SOURCE / name, positive / name
        if not a.is_file() or not b.is_file() or sha(a) != sha(b):
            raise ValueError('Retained acquisition differs: ' + name)
        source_hashes[name] = sha(a)
    result = read(positive / 'result.json')
    if result['case_id'] != CASE or result.get('provenance_kind') != 'synthetic_local_diagnostic':
        raise ValueError('Retained finalizer result identity/provenance mismatch')
    count = sum(1 for _ in (positive / 'trace.jsonl').open())
    if count != 36120:
        raise ValueError('Direct source must contain 36,120 frames')
    mapping_sha = sha(positive / 'video_frames.jsonl')
    source_audits = {}
    for i, video in enumerate(result['video_references']):
        receipt = positive / ('source-%d.json' % i)
        source_audits[video] = audit(positive / video, count,
                                    mapping_sha256=mapping_sha, receipt=receipt)
    proposal_case = next(case for case in read(WORK / 'proposals/cases.json')['cases']
                         if case['case_id'] == CASE)
    config = read(positive / 'config.json')
    request = {'case': proposal_case,
               'cell': {'cell_id': config['cell_id']}, 'actor': config['actor']}
    validate_attempt(positive, request, read(positive / 'construction.json'),
                     {'recorded_exit_code': 0}, {}, source_audits=source_audits)
    converted = positive / 'converted'
    process(positive, converted, REPO / 'runtime/library', validator,
            diagnostic_fixture=True)
    rendered = render(positive, converted, proposal_case)
    final = audit(rendered['video'], count, receipt=positive / 'final-decode.json')
    return {
        'format': 'c150142-current-runner-resumed-direct-long-core-v1',
        'passed': True, 'case_id': CASE, 'candidate_id': 'primary',
        'frames': count, 'source_sha256': source_hashes,
        'draft_manifest_sha256': sha(MANIFEST),
        'construction_sha256': entry['construction_sha256'],
        'source_decode_sha256': [sha(positive / ('source-%d.json' % i))
                                 for i in range(len(source_audits))],
        'final_decode_sha256': sha(positive / 'final-decode.json'),
        'final_video_sha256': final['video_sha256'],
        'core_decoder_checked': True,
        'scope': 'direct synthetic Core; official public fixture recipe still required',
        'delivery_ready': False,
        'original_native_observed': False,
        'physical_acceptance_claimed': False,
        'legal_acceptance_claimed': False,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--validator', required=True)
    args = parser.parse_args()
    configured = os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT')
    if not configured or not Path(configured).resolve().is_relative_to(
            (REPO / '.runtime-work').resolve()):
        raise ValueError('Export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work')
    print(json.dumps(run(args.output, args.validator), sort_keys=True, indent=2))
