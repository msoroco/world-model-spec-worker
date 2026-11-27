"""Materialize ten exact primary and controller fallback construction drafts."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

from author_semantic import AID, ACTOR, CAMERAS, CELL, HERE, LAW, RECORDING

ROOT = HERE.parents[1]
SOURCES = ('runner.py','outside_lane.py','reviewed_site.py','lane_native.py',
           'analysis.py','saved_audit.py',
           'tests/test_outside_lane.py','tests/test_saved_audit.py','tests/test_reviewed_site.py')


def encode(value):
    return json.dumps(value,indent=2,ensure_ascii=False)+'\n'


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(encode(value))
    return sha256(path.read_bytes()).hexdigest()


def run():
    plan=json.loads((HERE/'case-plan.json').read_text())
    selected=json.loads((HERE/'proposals/cases.json').read_text())['cases']
    by_id={case['case_id']:case for case in selected}
    entries=[]
    for index,item in enumerate(plan['cases']):
        case_id=item['case_id'];suffix=case_id.removeprefix(AID+'__')
        canonical=by_id[case_id]
        folder=HERE if index==0 else HERE/'cases'/suffix
        folder.mkdir(parents=True,exist_ok=True)
        for candidate,gain in (('primary',.025),('fallback1',.02)):
            config={'assignment_id':AID,'law_id':LAW,'cell_id':CELL,'actor':ACTOR,
                    'selected_case_id':case_id,'candidate_id':candidate,'steer_gain':gain,
                    'rate_hz':20,'duration_s':45,'frame_count':900,'required_atoms':[],
                    'source_packets':[],
                    'cameras':[{'name':name,'width':width,'height':height,'fov_deg':75,
                                'pose_strategy':'reviewed four-view body, lane function and solid-white separator coverage'}
                               for name,width,height in CAMERAS],
                    'supported_case_ids':[x['case_id'] for x in plan['cases']],
                    'recording_description':RECORDING,'case':canonical}
            files=[{'path':'config.json','content':encode(config)}]
            for name in SOURCES:
                files.append({'path':name,'content':(HERE/name).read_text(),
                              'source':str((HERE/name).relative_to(ROOT))})
            construction={'law_id':LAW,'cell_id':CELL,'actor':ACTOR,'case_id':case_id,
                          'status':'draft','entrypoint':'runner.py','files':files,
                          'recording_description':RECORDING,
                          'measurement_plan':{'purpose':'Source-bound original 20 Hz body, separator, lane-function and exception history',
                                              'case_ids':[case_id],
                                              'unresolved_legal_judgment':True},
                          'mechanisms':{'status':'source_gated_native_construction',
                                        'reviewed_site':'separate source-hashed authority, map, lane functions, solid-white line, driver and exception records',
                                        'controller':'finite route steering and speed target; requested setup not accepted outcome'},
                          'static_checks':['runner.py --check','reviewed source hashes and every route direction','offline bundle tests'],
                          'termination_rules':['900 original 20 Hz frames','fail closed on source or frame mismatch'],
                          'candidate_id':candidate}
            name='construction.json' if candidate=='primary' else 'fallback1-construction.json'
            construction_sha=write(folder/name,construction)
            if candidate=='primary':
                primary_path=folder/name
                primary_sha=construction_sha
                if index==0:
                    write(HERE/'config.json',config)
                    # Root runner.py already exists as the canonical source.
            else:
                fallback_path=folder/name
                fallback_sha=construction_sha
        requirements=[{'disposition_index':d['disposition_index'],
                       'requirement':d['requirement'],'source':d['source'],
                       'output_key':d['planned_channel'],
                       'method':'source_sealed_lane_measurement','value_type':'object',
                       'kind':'measured',
                       'inputs':['original-history.jsonl','original-source-receipt.json','trace.jsonl']}
                      for d in plan['requirement_dispositions']]
        contract={'format':'worker-measurement-contract','case_id':case_id,
                  'requirements':requirements,
                  'negative':{'remove':['original-history.jsonl'],
                              'error_contains':'Missing required source: original-history.jsonl'}}
        contract_path=folder/'measurement-contract.json'
        write(contract_path,contract)
        entries.append({'case_id':case_id,'kind':'delivery','status':'partial_cpu_preparation',
                        'construction':str(primary_path.relative_to(HERE)),
                        'construction_sha256':primary_sha,
                        'candidate_risk':item['physical_risk'],
                        'candidates':[{'id':'fallback1','construction':str(fallback_path.relative_to(HERE)),
                                       'construction_sha256':fallback_sha,
                                       'trigger':{'source':'original-attempt/physical-feedback.json',
                                                  'metric':'source-bound route convergence and camera coverage',
                                                  'failure_condition':'Primary steering cannot hold sourced route or reviewed views lose vehicle body'},
                                       'changed_knobs':['steer_gain .025 to .02']}],
                        'measurement_contract':str(contract_path.relative_to(HERE)),
                        'measurement_procedure':{'entrypoint':'analysis.py'},
                        'fixture_recipe':str((folder/'fixture-recipe.json').relative_to(ROOT)),
                        'native_handoff':{'python_env_var':'CARLA_PYTHON','host_env_var':'CARLA_HOST',
                                          'port_env_var':'CARLA_PORT',
                                          'reviewed_packet_env_var':'C3997_REVIEWED_SITE'}})
    runtime_sha=sha256((ROOT/'runtime/SOURCE-MANIFEST.json').read_bytes()).hexdigest()
    manifest={'format':'worker-execution-manifest','assignment_id':AID,
              'runtime_manifest_sha256':runtime_sha,'status':'partial_cpu_preparation',
              'semantic_index':'proposals/semantic-index.json','cases':entries,
              'comparisons':plan['comparisons']}
    write(HERE/'execution-manifest.draft.json',manifest)


if __name__=='__main__':run()
