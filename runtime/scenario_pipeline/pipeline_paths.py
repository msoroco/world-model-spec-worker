"""One configurable root for every persistent scenario-pipeline artifact.

SCENARIO_PIPELINE_OUTPUT_ROOT can relocate artifacts without moving source code.
It must be set consistently for imports, workers, finalization and packaging.
"""
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = REPO_ROOT.parent
OUTPUT_ROOT = Path(os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT',
                                  str(PROJECT_ROOT/'runs/scenario_pipeline'))).expanduser().resolve()
INPUTS_ROOT = OUTPUT_ROOT/'inputs'
CATALOG_DIR = INPUTS_ROOT/'catalog'
SHARED_INPUTS_DIR = INPUTS_ROOT/'shared'
STATE_PATH = OUTPUT_ROOT/'state/pipeline.sqlite'
RUNS_ROOT = OUTPUT_ROOT/'work'
RECORDINGS_ROOT = OUTPUT_ROOT/'recordings'
SETS_ROOT = OUTPUT_ROOT/'sets'


def require_artifact_path(path):
    """Reject persistent CLI destinations outside the configured artifact root."""
    candidate = Path(path).expanduser().resolve()
    if candidate != OUTPUT_ROOT and OUTPUT_ROOT not in candidate.parents:
        raise ValueError('Generated artifacts must be under '+str(OUTPUT_ROOT)+
                         '; set SCENARIO_PIPELINE_OUTPUT_ROOT consistently to use another root')
    relative=candidate.relative_to(OUTPUT_ROOT)
    if relative.parts and relative.parts[0] not in {'state','inputs','recordings','sets','work'}:
        raise ValueError('Use canonical storage: state, inputs, recordings, sets, or work')
    if candidate == REPO_ROOT or REPO_ROOT in candidate.parents or PROJECT_ROOT/'third_party' in candidate.parents:
        raise ValueError('Generated artifacts cannot be stored in source or third-party trees')
    return candidate


def initialize_inputs():
    """Copy versioned bootstrap inputs to the artifact root without overwriting updates."""
    copied = []
    for source in sorted((REPO_ROOT/'data/bootstrap').glob('*.json')):
        directory = SHARED_INPUTS_DIR if source.name in ('law_templates_draft.json', 'context_predicates_draft.json') else CATALOG_DIR
        target = require_artifact_path(directory/source.name)
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            with target.open('xb') as stream:
                stream.write(source.read_bytes())
            copied.append(str(target))
        except FileExistsError:
            pass
    return {'artifact_root': str(OUTPUT_ROOT), 'copied': copied}
