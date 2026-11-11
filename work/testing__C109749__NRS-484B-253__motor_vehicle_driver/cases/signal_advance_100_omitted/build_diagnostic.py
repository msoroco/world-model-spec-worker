"""Build the matched omitted-signal source from the 210-frame approach."""
import hashlib
import json
from pathlib import Path

folder = Path(__file__).resolve().parent
assignment = folder.parents[1]
source = assignment / 'cases/signal_advance_100_at/diagnostic.json'
case = assignment.name + '__signal_advance_100_omitted'


def compact(value):
    return json.dumps(value, separators=(',', ':'), allow_nan=False)


def build():
    spec = json.loads(source.read_text())
    history = [json.loads(line) for line in spec['files']['interaction_history.jsonl'].splitlines() if line]
    evidence = [json.loads(line) for line in spec['files']['capture/evidence.jsonl'].splitlines() if line]
    if len(history) != 210 or len(evidence) != 210:
        raise ValueError('Matched signal source requires all 210 samples')
    for row, event in zip(history, evidence):
        if row['frame'] != event['original_frame']:
            raise ValueError('Original frame join differs')
        row['ego_left_indicator'] = False
        for participant in event['original_observations']['participants']:
            if participant['actor_id'] == row['ego']['actor_id']:
                participant['light_attributes']['light_LeftBlinker'] = False
    spec['files']['interaction_history.jsonl'] = '\n'.join(map(compact, history)) + '\n'
    spec['files']['capture/evidence.jsonl'] = '\n'.join(map(compact, evidence)) + '\n'
    for index, graph in enumerate(spec['graphs']):
        frame = graph['attributes']['frame']
        event = evidence[(frame - history[0]['frame'])]
        graph['attributes']['observed_evidence'] = event['original_observations']
        for node in graph['nodes']:
            if node['id'] == 'ego':
                node['attributes']['light_LeftBlinker'] = False
    manifest = json.loads(spec['files']['capture/manifest.json'])
    manifest['case_id'] = case
    spec['files']['capture/manifest.json'] = compact(manifest) + '\n'
    provenance = json.loads(spec['files']['fixture-provenance.json'])
    provenance['scope'] = 'matched omitted-signal 210-frame software diagnostic; no physical acceptance'
    spec['files']['fixture-provenance.json'] = compact(provenance) + '\n'
    output = folder / 'diagnostic.json'
    output.write_text(compact(spec) + '\n')
    if output.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('Matched diagnostic exceeds 2 MiB source limit')
    name = 'work/' + assignment.name + '/cases/signal_advance_100_omitted/diagnostic.json'
    checksum = hashlib.sha256(output.read_bytes()).hexdigest()
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': 'diagnostic-input.json', 'source': name,
                           'sha256': checksum}],
              'generator': {'source': name, 'sha256': checksum}}
    (folder / 'diagnostic-recipe.json').write_text(json.dumps(recipe, indent=2) + '\n')
    print(json.dumps({'frames': 210, 'size_bytes': output.stat().st_size,
                      'diagnostic_sha256': checksum}))


if __name__ == '__main__':
    build()
