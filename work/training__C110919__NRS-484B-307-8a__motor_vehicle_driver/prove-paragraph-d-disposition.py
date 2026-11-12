"""Source-bound paragraph (d) applicability check for this authored ego actor."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
FROZEN=ROOT/'inputs/coverage/branch-sources.json'
RUNNER=HERE/'native/traffic_timing_sweep_runner.py'
PLAN=HERE/'case-plan.json'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def require(ok,message):
    if not ok:raise ValueError(message)

def main():
    source=json.loads(FROZEN.read_text())['laws']['NRS-484B-307-8d']['law']
    plan=json.loads(PLAN.read_text())
    runner=RUNNER.read_text()
    require(source['source']=='NRS 484B.307(8)(d)' and
            'motorcycle, moped or trimobile or riding a bicycle, an electric bicycle or an electric scooter' in source['text'] and
            'two complete cycles' in source['text'] and
            plan['actor']=='motor_vehicle_driver' and
            "library.find('vehicle.lincoln.mkz_2020')" in runner,
            'Frozen exception text or selected ego blueprint differs')
    disposition={'format':'c110919-paragraph-d-source-disposition-v1',
        'law_id':'NRS-484B-307-8d','frozen_source_sha256':sha(FROZEN),
        'runner_source_sha256':sha(RUNNER),'case_plan_sha256':sha(PLAN),
        'selected_ego_blueprint':'vehicle.lincoln.mkz_2020',
        'selected_ego_actor':'motor_vehicle_driver',
        'exception_subjects':['motorcycle','moped','trimobile','bicycle','electric bicycle','electric scooter'],
        'selected_ego_in_exception_subjects':False,
        'selected_ego_exception_route':'not_applicable_to_authored_Lincoln_ego',
        'case_plan_disposition':'exception_pending_until_original_actor_and_signal_readback',
        'two_cycles_simulated':False,'original_native_actor_verified':False,
        'legal_verdict_claimed':False}
    target=HERE/'update053-paragraph-d-disposition.json'
    target.write_text(json.dumps(disposition,indent=2)+'\n')
    print(json.dumps({'source_bound':True,'selected_ego_exception_applicable':False,
        'original_native_actor_verified':False,'proof_sha256':sha(target)}))

if __name__=='__main__':main()
