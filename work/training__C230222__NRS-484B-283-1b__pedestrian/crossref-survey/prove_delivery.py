"""Run diagnostic and missing-original controls for eight survey cases."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.parent
ROOT = ASSIGNMENT.parents[1]
RUNTIME = ROOT / '.runtime-work'
AUDIT = HERE / 'delivery_audit.py'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def locate(pattern, file, predicate):
    matches = [p for p in sorted(RUNTIME.glob(pattern)) if
               (p / file).is_file() and predicate(read(p / file))]
    if not matches:
        raise ValueError('Missing exact source: ' + pattern)
    return matches[-1]


def run():
    records = []
    for code in ('060a', '060b', '140b', '46'):
        entries = read(ASSIGNMENT / f'crossref-{code}-manifest.json')['cases']
        for entry in entries:
            case = entry['case_id']
            label = Path(entry['construction']).parent.name
            attempt = locate(f'c230222-crossref-{code}-{label}-compat*',
                             'compatibility.json', lambda x: x.get('passed') is True and
                             x.get('case_id') == case and x.get('candidate_id') == 'primary')
            saved = locate(f'c230222-crossref-{code}-{label}-saved*',
                           'v0001/processing.json', lambda x: x.get('passed') is True and
                           x.get('case_id') == case and x.get('candidate_id') == 'primary')
            processing = saved / 'v0001/processing.json'
            folder = HERE / code / label / 'delivery-proof'
            folder.mkdir(parents=True, exist_ok=True)
            base = [sys.executable, str(AUDIT), '--code', code, '--case', case,
                    '--candidate', 'primary', '--attempt', str(attempt),
                    '--processing', str(processing)]
            outputs = []
            for kind in ('positive', 'negative'):
                output = RUNTIME / f'c230222-survey-{code}-{label}-delivery-{kind}.json'
                if output.exists():
                    output.unlink()
                command = base + ['--output', str(output)] + (['--diagnostic'] if kind == 'positive' else [])
                log = folder / f'{kind}.log'
                with log.open('w') as stream:
                    result = subprocess.run(command, cwd=ROOT, stdout=stream,
                                            stderr=subprocess.STDOUT, timeout=30)
                expected = 0 if kind == 'positive' else 1
                if result.returncode != expected or (kind == 'negative' and
                        'Original Native source required' not in log.read_text()):
                    raise ValueError('Survey delivery proof failed: ' + str(log))
                outputs.append({'kind': kind, 'command': ' '.join(command),
                                'exit_code': result.returncode,
                                'log': str(log.relative_to(ASSIGNMENT)),
                                'log_sha256': sha(log),
                                'output': str(output.relative_to(ROOT)) if output.exists() else None,
                                'output_sha256': sha(output) if output.exists() else None})
            records.append({'case_id': case, 'code': code, 'label': label,
                            'construction_sha256': entry['construction_sha256'],
                            'attempt': str(attempt.relative_to(ROOT)),
                            'processing': str(processing.relative_to(ROOT)),
                            'processing_sha256': sha(processing),
                            'controls': outputs, 'diagnostic_only': True})
    target = HERE / 'delivery-proof-index.json'
    target.write_text(json.dumps({'format': 'c230222-survey-delivery-controls-v1',
                                  'cases': records, 'original_native_observed': False},
                                 indent=2) + '\n')
    print(json.dumps({'cases': len(records), 'index_sha256': sha(target)}))


if __name__ == '__main__':
    run()
