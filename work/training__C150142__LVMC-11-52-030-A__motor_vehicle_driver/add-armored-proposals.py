"""Add exact text-6 armored visual-proxy semantic proposals."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def build():
    path = ROOT / 'proposals/cases.json'
    document = json.loads(path.read_text())
    existing = {row['case_id']: row for row in document['cases']}
    result = []
    for sign in ('unsigned', 'signed'):
        for activity in ('business', 'no_business'):
            old = ROOT.name + '__emergency_vehicle_' + sign + '_' + activity
            new = ROOT.name + '__armored_car_' + sign + '_' + activity
            proposal = json.loads(json.dumps(existing[old]))
            proposal['case_id'] = new
            proposal['rationale'] = (
                'Armored-car text-6 diagnostic request: Sprinter body with four '
                'attached visible box panels, a 12-second red-curb stop, ' +
                ('authored armored-or-emergency sign, ' if sign == 'signed' else
                 'no exception sign, ') +
                ('service-worker approach/dwell/departure. ' if activity == 'business'
                 else 'empty service-worker inventory. ') +
                'This is an armored-looking proxy. Actual armor, statutory vehicle '
                'identity, business purpose, necessity, physical pixels and legal '
                'outcome remain unverified.')
            proposal['variable_assignments']['service_class']['value'] = 'armored_car'
            proposal['variable_assignments']['road_and_actors']['value'] = (
                ('authored red curb with armored-or-emergency sign; ' if sign == 'signed'
                 else 'authored red curb without exception sign; ') +
                'Sprinter with four attached panels' +
                (' and service worker' if activity == 'business'
                 else ' and empty service-worker inventory'))
            construction = json.loads((ROOT / 'selected-primary' /
                                       ('armored_car_' + sign + '_' + activity) /
                                       'construction.json').read_text())
            proposal['recording_description'] = construction['recording_description']
            proposal['unresolved_judgment_calls'] = [
                'An armored-looking visual proxy does not establish statutory armored-car identity.',
                'Actual business purpose, necessary duration and sign visibility require source review.']
            if new in existing:
                if existing[new] != proposal:
                    raise ValueError('Existing armored proposal differs: ' + new)
                result.append({'case_id': new, 'added': False})
            else:
                document['cases'].append(proposal)
                result.append({'case_id': new, 'added': True})
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + '\n')
    return result


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))
