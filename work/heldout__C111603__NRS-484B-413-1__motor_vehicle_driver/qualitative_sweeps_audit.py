"""Source-bound finite engineering sweeps for clearance and signal mechanism."""
from hashlib import sha256
import json
from pathlib import Path
from comparison_audit import audit as compare, load_case, rows
from listener_sweep_audit import audit as listener_sweep

HERE=Path(__file__).resolve().parent


def sha(path): return sha256(path.read_bytes()).hexdigest()


def require(condition,message):
    if not condition: raise ValueError(message)


def audit(folder=HERE):
    folder=Path(folder)
    saved=json.loads((folder/'saved-comparison-proof.json').read_text())
    covered=saved['comparisons']
    needed=('reasonable_safety_clearance','vehicle_indicator','vehicle_signal_alternative',
            'pedestrian_horn_audio','both_affected_conjunction','pedestrian_listener_distance',
            'indicator_activation_timing')
    require(all(key in covered for key in needed),'Current saved comparison sweep proofs missing')
    span=json.loads((folder/'clearance-span-audit.json').read_text())
    require(span['original_source_pair_audits_passed'] is True and
            span['physical_safety_verified'] is False,
            'Clearance span is stale or overclaimed')
    gap=span['minimum_sampled_gap_m']
    require(gap['narrow']<gap['baseline']<gap['wide'] and gap['wide']>0,
            'Three point original clearance sweep does not span positive gap')
    safety=compare('reasonable_safety_clearance')
    require(safety['measured_values']['minimum_sampled_gap_m']==[gap['wide'],gap['narrow']],
            'Current source clearance pair differs from span')
    indicator=compare('vehicle_indicator')
    alternative=compare('vehicle_signal_alternative')
    ids={case.rsplit('__',1)[-1]:case for case in
         indicator['case_ids']+alternative['case_ids']}
    require(set(ids)=={'vehicle_left_indicator','vehicle_no_indicator','vehicle_hand_signal'},
            'Signal mechanism sweep needs three exact source cases')
    require(indicator['case_ids'][0]==alternative['case_ids'][0],
            'Signal sweep baseline case changed')
    mechanisms={}
    for short,case in ids.items():
        files,videos,source=load_case(case)
        signals=rows(files,'ego_signal_audio.jsonl')
        hand=rows(files,'hand_signal_original.jsonl') if 'hand_signal_original.jsonl' in files else []
        state=sorted({row['indicator_readback'] for row in signals})
        mechanisms[short]={'case_id':case,'indicator_readback':state,
                           'hand_source_frames':len(hand),'diagnostic_source':source,
                           'saved_original_source_sha256':
                               covered['vehicle_indicator' if short=='vehicle_no_indicator'
                                       else 'vehicle_signal_alternative']['fixed_sources']}
    require(mechanisms['vehicle_no_indicator']['indicator_readback']==['off'] and
            mechanisms['vehicle_left_indicator']['indicator_readback']!=['off'] and
            mechanisms['vehicle_hand_signal']['hand_source_frames']>0,
            'Three signal mechanisms lack original readback contrast')
    timing=compare('indicator_activation_timing')
    require(timing['measured_values']['activation_frame_index']==[2,4,6] and
            timing['measured_values']['diagnostic_pre_turn_indicator_frames']==[4,2,0],
            'Indicator activation timing sweep lacks exact source contrast')
    listener=listener_sweep(folder)
    pedestrian_points=listener['points']
    require([point['offset_m'] for point in pedestrian_points]==[2,4,6] and
            len({point['minimum_sampled_ped_gap_m'] for point in pedestrian_points})==3,
            'Pedestrian effect proxy sweep lacks three measured body gaps')
    horn=compare('pedestrian_horn_audio')
    both=compare('both_affected_conjunction')
    horn_rms=horn['measured_values']['pre_turn_listener_rms']
    both_rms=both['measured_values']['pre_turn_listener_rms']
    require(horn_rms[0]>horn_rms[1]>=0 and both_rms[0]>both_rms[1]>=0,
            'Original listener PCM conditional audio contrast missing')
    for short in ('clearance_narrow','vehicle_left_indicator','clearance_wide'):
        files,_,_=load_case(HERE.name+'__'+short)
        require(json.loads(files['affected_participants.json'])['vehicle_may_be_affected'] is True,
                'Vehicle body-gap proxy lacks sourced possible-effect context')
    return {'format':'worker-turn-qualitative-sweeps',
            'reasonable_safety':{'minimum_sampled_surface_gap_m':gap,
                'clearance_span_sha256':sha(folder/'clearance-span-audit.json'),
                'comparison_proof_sha256':sha(folder/'comparison-reasonable_safety_clearance-proof.json')},
            'appropriate_signal':{'mechanisms':mechanisms,
                'indicator_activation_frame_index':[2,4,6],
                'diagnostic_pre_turn_indicator_frames':[4,2,0],
                'native_preturn_timing_verified':False,
                'activation_comparison_sha256':sha(folder/'comparison-indicator_activation_timing-proof.json'),
                'indicator_comparison_sha256':sha(folder/'comparison-vehicle_indicator-proof.json'),
                'hand_comparison_sha256':sha(folder/'comparison-vehicle_signal_alternative-proof.json')},
            'clearly_audible_signal':{'pre_turn_listener_rms_horn_and_no_horn':horn_rms,
                'pre_turn_listener_rms_both_affected':both_rms,
                'pedestrian_distance_offsets_m':[point['offset_m'] for point in pedestrian_points],
                'audibility_judgment':None},
            'any_pedestrian_may_be_affected':{'minimum_sampled_ped_gap_m':
                [point['minimum_sampled_ped_gap_m'] for point in pedestrian_points],
                'possible_effect_judgment':None},
            'any_other_vehicle_may_be_affected':{'minimum_sampled_vehicle_gap_m':gap,
                'possible_effect_judgment':None},
            'saved_comparison_proof_sha256':sha(folder/'saved-comparison-proof.json'),
            'diagnostic_fixture':True,'physical_safety_verified':False,
            'signal_appropriateness_verified':False,'legal_acceptance_claimed':False,
            'engineering_proxy_only':True}


if __name__=='__main__':
    result=audit()
    (HERE/'qualitative-sweeps-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print('five_qualitative_engineering_source_sweeps_passed')
