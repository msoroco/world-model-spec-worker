"""Audit four saved synthetic controlled comparisons for official alternative."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    results = []
    for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        first = HERE / 'saved-fixtures/official_1' / candidate
        second = HERE / 'saved-fixtures/official_2' / candidate
        a, b = rows(first / 'actor-frames.jsonl'), rows(second / 'actor-frames.jsonl')
        assert len(a) == len(b) == 480
        assert all(x['approach'] == y['approach'] and
                   x['front_red_flash_on'] == y['front_red_flash_on'] and
                   x['time_s'] == y['time_s'] for x, y in zip(a, b))
        assert a[0]['subject'] == b[0]['subject']
        assert a[100]['subject']['y_m'] != b[100]['subject']['y_m']
        config_a = json.loads((first / 'config.json').read_text())
        config_b = json.loads((second / 'config.json').read_text())
        assert config_a['candidate_id'] == config_b['candidate_id'] == candidate
        assert config_a['cell_id'] == config_b['cell_id'] == 'C405647'
        assert config_a['actor'] == config_b['actor'] == 'motor_vehicle_driver'
        assert config_a['law_id'] == config_b['law_id'] == 'NRS-484B-267-1a'
        assert config_a['duration_s'] == config_b['duration_s'] == 24
        assert config_a['rate_hz'] == config_b['rate_hz'] == 20
        report_a = json.loads((first / 'analysis-report.json').read_text())
        report_b = json.loads((second / 'analysis-report.json').read_text())
        ma = report_a['measurements']['official_approach_clearance']['value']
        mb = report_b['measurements']['official_approach_clearance']['value']
        assert ma['catchup_frame'] == mb['catchup_frame']
        assert ma['full_body_cleared_before_catchup'] is True
        assert mb['full_body_cleared_before_catchup'] is False
        results.append({'candidate_id': candidate,
                        'fixed_approach_sha256': hashlib.sha256(''.join(
                            json.dumps(row['approach'], sort_keys=True) + '\n' for row in a).encode()).hexdigest(),
                        'first_report_sha256': sha(first / 'analysis-report.json'),
                        'second_report_sha256': sha(second / 'analysis-report.json'),
                        'controlled_difference': 'subject full-body clearance before catchup'})
    return {'passed': True, 'controlled_pairs': results,
            'agency_authority_or_lamp_qualification_verified': False,
            'legal_yield_verdict': None}


if __name__ == '__main__':
    print(json.dumps(audit(), sort_keys=True))
