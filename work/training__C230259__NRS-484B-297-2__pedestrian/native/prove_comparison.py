"""CPU positive and negative tests of the independent raw-source comparison."""

import json
import tempfile
from pathlib import Path

from audit_comparison import audit
from prove_saved_walking import BASE, prepare, write


def prove():
    with tempfile.TemporaryDirectory(prefix='c230259-comparison-', dir='.runtime-work') as scratch:
        a, b = Path(scratch) / 'a', Path(scratch) / 'b'
        a.mkdir()
        b.mkdir()
        prepare(a, 'a')
        prepare(b, 'b')
        positive = audit(a, b)
        path = b / 'walking-source.jsonl'
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        rows[50]['vehicle_xy_m'][0] += 1
        path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        try:
            audit(a, b)
        except ValueError as error:
            wrong_vehicle = str(error)
            assert wrong_vehicle == 'Comparison fixed participant source differs: vehicle_xy_m'
        else:
            raise AssertionError('Changed vehicle route was accepted')
        path.unlink()
        try:
            audit(a, b)
        except ValueError as error:
            missing_trace = str(error)
            assert missing_trace == 'Missing comparison source: walking-source.jsonl'
        else:
            raise AssertionError('Missing trace was accepted')
        return {'format': 'worker-independent-side-comparison-cpu-proof',
                'assignment_id': BASE.name, 'positive': positive,
                'negative': [wrong_vehicle, missing_trace],
                'physical_completion': False}


if __name__ == '__main__':
    proof = prove()
    write(BASE / 'native' / 'comparison-proof.json', proof)
    print(json.dumps({'positive': proof['positive']['passed'],
                      'negative_rejections': len(proof['negative'])}))
