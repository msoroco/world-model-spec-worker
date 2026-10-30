"""Bind all declared required Core atoms to actual original capture implementations."""
import json,pathlib
R=pathlib.Path(__file__).resolve().parents[2]
ids=json.loads((R/'partitions/demo-test-04.json').read_text())['assignment_ids']+['testing__C24811__NRS-484B-250-4__motor_vehicle_driver','testing__C376646__NRS-484B-250-4__motor_vehicle_driver']
methods={
'ru.subject':('PipelineCapture.capture original subject actor identity','capture/evidence.jsonl subject identity joins original Native actor and trace.jsonl'),
'env.wet_road':('PipelineCapture.capture original weather get_weather wetness readback','capture/evidence.jsonl environment and following_samples.jsonl original_weather, same original ticks'),
'dev.speed_limit_sign':('PipelineCapture.capture original native device inventory and OpenDRIVE speed sign landmark readback','capture/evidence.jsonl original_observations.devices and posted_speed_context.json native_landmarks; rendered sign authority remains independent check'),
'dev.traffic_signal':('PipelineCapture.capture original native signal actor identity and get_state readback','capture/evidence.jsonl device inventory plus signal_history.jsonl or interaction_history.jsonl original head identity and indications'),
'dev.governs':('Native traffic light get_affected_lane_waypoints readback in runner','signal_context.json affected_lanes and same-original-frame head state records; not inferred from proximity'),
'st.one_way_roadway':('Native generated connected road readback plus scenario_geometry directed_roadways','scenario_geometry.json source geometry and road.xodr; rendered and physical roadway verification pending'),
'st.stop_line':('Physical accepted road-line mesh construction with Native transforms and original geometry capture','signal_context.json physical_stopline_tiles and road.xodr; absent higher-priority references explicitly recorded per selected case'),
'st.sight_distance':('Native original driver viewpoint cast_ray histories and sampled candidate scan','interaction_history.jsonl sight_ray and sight_candidates with original frame/time, observer and hits; no continuous legal visibility threshold'),
'rel.visible':('Native original cast_ray to actual target vehicle excluding own/target body hits','interaction_history.jsonl sight_ray hits, viewpoint and target; geometric rays do not prove pixels or human perception'),
'kin.speed':('PipelineCapture.capture original actor.get_velocity norm','trace.jsonl speed_mps and original velocity acquisition'),
'kin.velocity':('PipelineCapture.capture original actor.get_velocity components','trace.jsonl velocity_mps, same original tick'),
}
for aid in ids:
 f=R/'work'/aid;p=f/'execution-manifest.json';m=json.loads(p.read_text())
 for entry in m['cases']:
  construction=json.loads((f/entry['construction']).read_text());cfg=json.loads(next(x['content'] for x in construction['files'] if x['path']=='config.json'))
  for atom in cfg['required_atoms']:
   if atom not in entry['acquisition']:
    method,evidence=methods[atom];entry['acquisition'][atom]=dict(entrypoint='runner.py',method=method,evidence=evidence)
 p.write_text(json.dumps(m,indent=2)+'\n')
 print(aid,'all required acquisition paths bound')
