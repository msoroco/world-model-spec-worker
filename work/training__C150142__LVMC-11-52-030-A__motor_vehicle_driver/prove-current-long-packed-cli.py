"""Audit the pinned fixture/compatibility CLI behavior on compact long sources."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
RECIPE = HERE / 'current-tour-bus-below-packed-fixture-recipe.json'
FIXTURE = REPO / '.runtime-work/owner150142/packed-fixture-cli-v1'
FIXTURE_LOG = HERE / 'current-long-packed-fixture-cli.log'
COMPATIBILITY_LOG = HERE / 'current-long-packed-compatibility-cli.log'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    recipe = json.loads(RECIPE.read_text())
    output = json.loads(FIXTURE_LOG.read_text())
    if recipe['format'] != 'worker-fixture-recipe' or len(recipe['sources']) != 9:
        raise ValueError('Packed recipe differs')
    if output['recipe_sha256'] != sha(RECIPE):
        raise ValueError('Pinned CLI materialized another recipe')
    for item in recipe['sources']:
        source = REPO / item['source']
        target = FIXTURE / item['path']
        if sha(source) != item['sha256'] or sha(target) != item['sha256']:
            raise ValueError('Packed materialization changed source: ' + item['path'])
    if (FIXTURE / 'video_frames.jsonl').exists() or (FIXTURE / 'overview.mkv').exists():
        raise ValueError('Pinned CLI unexpectedly expanded a packed source')
    failure = COMPATIBILITY_LOG.read_text()
    if ('package_compatibility.py' not in failure or
            'prepare_video(output)' not in failure or
            'FileNotFoundError' not in failure or
            'packed-fixture-compatibility-cli-v2/video_frames.jsonl' not in failure):
        raise ValueError('Compatibility failure is not the expected pre-analysis source gap')
    print(json.dumps({
        'format': 'c150142-packed-long-cli-path-proof-v1',
        'case_id': HERE.name + '__tour_bus_below',
        'recipe_sha256': sha(RECIPE),
        'fixture_cli_log_sha256': sha(FIXTURE_LOG),
        'compatibility_cli_log_sha256': sha(COMPATIBILITY_LOG),
        'packed_sources_materialized': 9,
        'source_expansion_before_video_preparation': False,
        'compatibility_failure': 'missing expanded video_frames.jsonl before analysis',
        'official_compatibility_passed': False,
    }, indent=2))


if __name__ == '__main__':
    main()
