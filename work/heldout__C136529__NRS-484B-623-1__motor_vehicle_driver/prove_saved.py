"""Execute the full saved-only path for the exact primary case and fallbacks."""
import json
import os
from pathlib import Path
import sys
import tempfile

folder=Path(__file__).resolve().parent
repo=folder.parents[1]
work=repo/'.runtime-work'
work.mkdir(exist_ok=True)
os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']=str(work/'adapter/c136529-saved')
sys.path.insert(0,str(repo/'runtime/scenario_pipeline'))
sys.path.insert(1,str(repo/'runtime/python'))
from worker_exchange.fixture_recipe import materialize as make_fixture
from worker_exchange.runtime_cli import materialize as make_attempt
from worker_exchange.saved_processing import copy_sources,run as process_saved
manifest=folder/'execution-manifest.json'
decoder=work/'fire-decoder/.lake/build/bin/adapterCheck'
if not decoder.is_file():raise ValueError('Pinned Lean decoder missing')
with tempfile.TemporaryDirectory(prefix='c136529-saved-',dir=work) as temp:
    base=Path(temp)
    for branch,recipe in (
        ('slow_with_following_traffic',folder/'diagnostic-recipe.json'),
        ('flowing_reference',folder/'cases/flowing_reference/diagnostic-recipe.json')):
        case=folder.name+'__'+branch
        branch_dir=base/branch;branch_dir.mkdir()
        fixture=branch_dir/'fixture'
        make_fixture(repo,recipe,fixture)
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            attempt=branch_dir/(candidate+'-attempt');output=branch_dir/(candidate+'-processed')
            make_attempt(manifest,case,attempt,candidate=candidate)
            copy_sources(fixture,attempt)
            assert not (attempt/'ego_speed_mps.jsonl').exists()
            receipt=process_saved(manifest,case,attempt,output,repo/'runtime/library',decoder)
            assert receipt['passed'] and receipt['candidate_id']==candidate
            assert receipt['originals_preserved'] and not receipt['missing_evidence']
            assert receipt['timestamp_joins']['frames']==9
            assert receipt['final_video_checks']['passed']
            assert not (attempt/'ego_speed_mps.jsonl').exists()
            stage=Path(receipt['analysis_directory'])
            result=json.loads((stage/'result.json').read_text())
            assert result['physical_acceptance_claimed'] is False
            assert result['legal_acceptance_claimed'] is False
            for name in ('ego_speed_mps','follower_speed_mps','follower_gap_m'):
                assert len((stage/(name+'.jsonl')).read_text().splitlines())==9
            print(branch,candidate,'saved_processing_passed',receipt['timestamp_joins']['frames'])
