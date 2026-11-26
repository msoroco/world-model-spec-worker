"""Bind passing current-runtime selected compatibility receipts to this package."""

import hashlib
import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def copy_clean(source, destination):
    text = source.read_text().rstrip() + '\n'
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text)
    return sha(destination)


def acquisition():
    channels = ('kin.position', 'kin.speed', 'ru.subject', 'st.sidewalk',
                'st.highway', 'rel.occupies', 'kin.heading',
                'st.lane_direction', 'rel.oncoming')
    result = {}
    for channel in channels:
        runner = channel in ('kin.position', 'kin.speed', 'ru.subject')
        result[channel] = {
            'entrypoint': 'runner.py' if runner else 'saved_walking.py',
            'method': ('Original pedestrian actor ID, transform and velocity sampled '
                       'at every synchronized source frame' if runner else
                       'Source-joined walking trace, reviewed highway and sidewalk '
                       'packet, opposing vehicle route and original camera frames'),
            'evidence': ('capture/evidence.jsonl, trace.jsonl and video_frames.jsonl'
                         if runner else
                         'walking-source.jsonl, reviewed-road-source.json, '
                         'video_frames.jsonl and four original camera sources'),
        }
    return result


def main():
    manifest_path = BASE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for side, entry in zip('ab', manifest['cases']):
        for candidate_id, selected in [('primary', entry),
                                       ('fallback1', entry['candidates'][0])]:
            output = ROOT / f'.runtime-work/c230259-297-2-compat-{side}-{candidate_id}-final'
            proof = json.loads((output / 'compatibility.json').read_text())
            if (not proof['passed'] or proof['case_id'] != entry['case_id'] or
                    proof['candidate_id'] != candidate_id):
                raise ValueError('Selected compatibility proof is not for this case/candidate')
            if proof['construction_sha256'] != selected['construction_sha256']:
                raise ValueError('Selected compatibility construction changed')
            receipt = BASE / f'selected-proofs/{side}-{candidate_id}-compatibility.json'
            analysis = BASE / f'selected-proofs/{side}-{candidate_id}-analysis.log'
            negative = BASE / f'selected-proofs/{side}-{candidate_id}-negative.log'
            copy_clean(output / 'compatibility-analysis.log', analysis)
            copy_clean(output / 'negative-analysis.log', negative)
            # The public receipt binds the original analysis and negative log bytes.
            if sha(analysis) != proof['log_sha256'] or sha(negative) != proof['negative_log_sha256']:
                raise ValueError('Log normalization would invalidate public proof')
            copy_clean(output / 'compatibility.json', receipt)
            offline = ROOT / f'.runtime-work/c230259-297-2-offline-{side}-{candidate_id}-final/offline.log'
            offline_log = BASE / f'selected-proofs/{side}-{candidate_id}-offline.log'
            copy_clean(offline, offline_log)
            selected['offline'] = {
                'command': '.venv-cpu/bin/python -B runtime.py offline --manifest '
                           f'work/{BASE.name}/execution-manifest.json --case {entry["case_id"]} '
                           f'--candidate {candidate_id} --output "$OFFLINE_OUT"',
                'exit_code': 0, 'construction_sha256': selected['construction_sha256'],
                'log': str(offline_log.relative_to(BASE)), 'log_sha256': sha(offline_log),
            }
            selected['compatibility'] = {
                'receipt': str(receipt.relative_to(BASE)), 'sha256': sha(receipt),
                'log': str(analysis.relative_to(BASE)),
            }
            if candidate_id == 'fallback1':
                selected['compatibility']['negative_log'] = str(negative.relative_to(BASE))
            selected['negative'] = {'log': str(negative.relative_to(BASE))}
        entry['acquisition'] = acquisition()
    write(manifest_path, manifest)
    print(json.dumps({'cases_bound': [entry['case_id'] for entry in manifest['cases']]}))


if __name__ == '__main__':
    main()
