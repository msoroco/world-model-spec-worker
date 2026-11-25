"""Exercise three pinned caravan completion outcomes and synthetic closure order."""
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[1]
STAGE = REPO / '.runtime-work/c160013-physical-preparation'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def run():
    root = Path(os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT', '/')).resolve()
    if not root.is_relative_to(REPO / '.runtime-work'):
        raise ValueError('Export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work')
    sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
    from worker_exchange.native_output import assess_physical
    manifest_path = PACKAGE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    lines = []
    prepared = []
    for label, suffix in (('wide', 'entrant_can_occupy_gap'),
                          ('narrow', 'entrant_cannot_occupy_gap')):
        entry = next(e for e in manifest['cases'] if e['case_id'].endswith('__' + suffix))
        saved_ref = entry['saved_processing']
        saved_path = PACKAGE / saved_ref['receipt']
        saved = json.loads(saved_path.read_text())
        if (sha(saved_path) != saved_ref['sha256'] or saved.get('passed') is not True or
                saved.get('recorded_only') is not True or saved.get('case_id') != entry['case_id'] or
                'saved_processing_started' not in saved.get('events', [])):
            raise ValueError('Recorded-only source rebuild required for ' + suffix)
        construction = json.loads((PACKAGE / entry['construction']).read_text())
        config = json.loads(next(item['content'] for item in construction['files']
                                 if item['path'] == 'config.json'))
        fixture = PACKAGE / 'cases/fixtures' / label
        fixtures = []
        for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
            stage = STAGE / label / kind
            stage.mkdir(parents=True, exist_ok=True)
            for name in ('caravan_history.jsonl', 'video_frames.jsonl', 'trace.jsonl',
                         'caravan_context.json'):
                shutil.copyfile(fixture / name, stage / name)
            write(stage / 'config.json', config)
            history = stage / 'caravan_history.jsonl'
            if kind == 'incomplete_motion':
                rows = [json.loads(line) for line in history.read_text().splitlines()]
                if label == 'wide':
                    for row in rows:
                        row['participants']['entrant']['lane_id'] = -2
                else:
                    first = rows[0]['participants']['entrant']['body_vertices_m']
                    for row in rows:
                        row['participants']['entrant']['body_vertices_m'] = first
                history.write_text(''.join(json.dumps(row) + '\n' for row in rows))
            elif kind == 'missing_evidence':
                (stage / 'caravan_context.json').unlink()
            value = assess_physical(stage, config, [{'matched': True}])
            value['provenance_kind'] = 'synthetic_fixture'
            value['diagnostic_fixture'] = True
            expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                        'missing_evidence': 'unverified'}[kind]
            status = value['physical_checks']['maneuver']['status']
            if status != expected or value['maneuver_completed'] != (expected == 'met'):
                raise ValueError(suffix + ' ' + kind + ': ' + status + ' rather than ' + expected)
            relative = 'cases/' + suffix + '-' + kind + '-physical-result.json'
            output = PACKAGE / relative
            write(output, value)
            fixtures.append({'kind': kind, 'command': 'PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/' +
                             PACKAGE.name + '/cases/prove_physical_preparation.py',
                             'log': 'cases/physical-preparation.log', 'exit_code': 0,
                             'result': relative, 'result_sha256': sha(output)})
            lines.append(suffix + ' ' + kind + ': ' + status + '; result_sha256=' + sha(output))
        lines.append(suffix + ': recorded-only receipt ' + sha(saved_path) +
                     ' proves saved_processing_started in synthetic diagnostic processing')
        prepared.append((entry, suffix, fixtures))
    native = (PACKAGE / 'caravan_native.py').read_text()
    if not (native.index('restoration = restore(client, saved)') < native.index('seal_capture(output')):
        raise ValueError('Native seal does not follow restoration')
    lines.append('Source order checked: capture frame loop and encoders close before restoration and seal; '
                 'native exit and owner release precede saved processing in the runtime contract. '
                 'Synthetic CPU test; no actual Native ownership release claimed.')
    log = PACKAGE / 'cases/physical-preparation.log'
    log.write_text('\n'.join(lines) + '\n')
    for entry, suffix, fixtures in prepared:
        for fixture in fixtures:
            fixture['log_sha256'] = sha(log)
        receipt = {'format': 'worker-physical-preparation', 'case_id': entry['case_id'],
                   'construction_sha256': entry['construction_sha256'],
                   'fixtures': fixtures,
                   'lifecycle': {'events': ['capture_finished', 'encoders_closed',
                                            'restoration_verified', 'native_exit',
                                            'owner_released', 'saved_processing_started'],
                                 'exit_code': 0, 'log': 'cases/physical-preparation.log',
                                 'log_sha256': sha(log)}}
        relative = 'cases/' + suffix + '-physical-preparation.json'
        path = PACKAGE / relative
        write(path, receipt)
        entry['physical_preparation'] = {'receipt': relative, 'sha256': sha(path)}
    write(manifest_path, manifest)
    print('\n'.join(lines))


if __name__ == '__main__':
    run()
