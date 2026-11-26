"""Build controlled lateral-clearance fallbacks for each selected pass."""
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CASES = {'bicycle_pass_wide': -1.5,
         'electric_bicycle_pass_wide': -1.5,
         'electric_bicycle_pass_narrow': -3.55}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    results = []
    for suffix, rider_y in CASES.items():
        family = 'draft-bicycle' if suffix.startswith('bicycle') else 'draft-ebike'
        source = ROOT / family / suffix / 'primary/construction.json'
        construction = copy.deepcopy(json.loads(source.read_text()))
        config_file = next(item for item in construction['files'] if item['path'] == 'config.json')
        config = json.loads(config_file['content'])
        assert config['rider_y_m'] != rider_y
        config['rider_y_m'] = rider_y
        config['candidate_id'] = 'fallback1'
        config_file['content'] = json.dumps(config, indent=2) + '\n'
        construction['mechanisms'].append('Fallback shifts rider center laterally within the same one-way through lane for greater surface clearance')
        construction['status'] = 'selected_cpu_fallback_diagnostic'
        target = ROOT / family / suffix / 'fallback1/construction.json'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(construction, indent=2) + '\n')
        results.append({'case_id': construction['case_id'], 'construction_sha256': sha(target),
                        'rider_y_m': rider_y})
    print(json.dumps(results, sort_keys=True))


if __name__ == '__main__':
    main()
