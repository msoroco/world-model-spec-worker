"""Independent hash, frame, geometry and boundary audit of copied saved fixtures."""
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    return [json.loads(x) for x in Path(path).read_text().splitlines()]


def audit():
    copied = read(HERE/'offline/manifest.json')
    saved_proof = read(HERE/'offline/saved-proof.json')
    compatibility = read(HERE/'offline/saved-compatibility.json')
    if saved_proof['copied_manifest_sha256'] != sha(HERE/'offline/manifest.json') or \
       compatibility['positive'] != 8 or compatibility['tamper_negative'] != 56 or \
       len(copied['entries']) != 8 or len(saved_proof['entries']) != 8:
        raise ValueError('saved audit source/proof')
    total = 0
    relations = {}
    for entry, proof in zip(copied['entries'], saved_proof['entries']):
        bundle = HERE/entry['bundle']
        witness, candidate = bundle.parent.name, bundle.name
        raw = HERE/'offline/raw-fixtures'/witness/candidate
        saved = HERE/'offline/saved-fixtures'/witness/candidate
        if (entry['case_id'], entry['candidate_id']) != \
           (proof['case_id'], proof['candidate_id']):
            raise ValueError('case order')
        if any(sha(raw/name) != digest for name, digest in proof['raw_hashes'].items()) or \
           any(sha(saved/name) != digest for name, digest in proof['saved_hashes'].items()):
            raise ValueError('fixture copy hashes')
        receipt = read(saved/'preparation-receipt.json')
        observed = rows(saved/'native-observed.jsonl')
        video = rows(saved/'camera-frames.jsonl')
        review = rows(saved/'frame-review.jsonl')
        raw_actor = rows(raw/'native-raw-actors.jsonl')
        raw_video = rows(raw/'video_frames.jsonl')
        raw_review = rows(raw/'frame-review.jsonl')
        if not all(len(x) == 240 for x in
                   (observed, video, review, raw_actor, raw_video, raw_review)):
            raise ValueError('saved frame coverage')
        if receipt['source_kind'] != 'synthetic_cpu' or \
           receipt['original_native_observed'] or receipt['delivery_ready'] or \
           receipt['config_sha256'] != sha(bundle/'config.json'):
            raise ValueError('saved receipt provenance')
        full = []
        passes = 0
        reviewed = 0
        for i, (actor, frame, view, source_actor, source_video, source_review) in \
                enumerate(zip(observed, video, review, raw_actor, raw_video, raw_review)):
            if actor['ego'] != source_actor['ego'] or actor['lead'] != source_actor['lead'] or \
               actor['observed_ego_lane_id'] != source_actor['observed_ego_lane_id'] or \
               view != source_review or actor['frame'] != frame['frame'] != view['frame'] != i or \
               actor['native_frame'] != frame['native_frame'] != view['native_frame'] != \
                   source_video['native_frame'] or \
               frame['video_frame'] != source_video['video_frame'] != i:
                raise ValueError('raw-to-saved frame or body change')
            ego = actor['ego']['body_native_xyz_m']
            lead = actor['lead']['body_native_xyz_m']
            full.append(actor['observed_ego_lane_id'] == -2 and
                        min(p[1] for p in ego) >= -7 and
                        max(p[1] for p in ego) <= -3.5)
            passes += int(min(p[0] for p in ego) > max(p[0] for p in lead) and
                          max(p[1] for p in ego) < min(p[1] for p in lead))
            reviewed += int(view['boundary_pixel_reviewed'] and
                            view['pavement_pixel_reviewed'])
            total += 1
        measured = proof['measurement']
        if measured['source_kind'] != 'synthetic_cpu' or measured['delivery_ready'] or \
           measured['full_body_unmarked_frames'] != sum(full) or \
           measured['right_pass_frames'] != passes or \
           measured['reviewed_boundary_pavement_frames'] != reviewed or \
           len(measured['spans']) != 1:
            raise ValueError('independent measurement counts')
        span = measured['spans'][0]
        occupied = [i for i, value in enumerate(full) if value]
        start, end = occupied[0], occupied[-1]
        centers = [observed[i]['ego']['center_native_xyz_m'] for i in range(start, end+1)]
        distance = sum(math.dist(a[:2], b[:2]) for a, b in zip(centers, centers[1:]))
        before = observed[max(0, start-1)]['ego']['center_native_xyz_m']
        after = observed[min(239, end+1)]['ego']['center_native_xyz_m']
        uncertainty = math.dist(before[:2], centers[0][:2]) + \
                      math.dist(centers[-1][:2], after[:2])
        if span['first_frame'] != start or span['last_frame'] != end or \
           not math.isclose(span['sampled_distance_lower_m'], distance, abs_tol=1e-6) or \
           not math.isclose(span['boundary_uncertainty_m'], uncertainty, abs_tol=1e-6):
            raise ValueError('independent distance')
        relation = ('incomplete_exit' if end == 239 else
                    'within_200ft' if distance+uncertainty <= 60.96 else
                    'over_200ft' if distance > 60.96 else 'ambiguous')
        if span['boundary_relation'] != relation or \
           span['distance_upper_m'] != (round(distance+uncertainty, 6) if end < 239 else None):
            raise ValueError('boundary classification')
        route = proof['routing']
        triggers = route['triggers']
        if (route['selected_fallback'] is not None or route['delivery_ready'] or
            route['measured_boundary_relation'] != relation or
            triggers['fallback1']['eligible'] !=
                (passes < 1 or relation in ('ambiguous', 'incomplete_exit', 'missing_or_multiple_spans')) or
            triggers['fallback2']['eligible'] != (reviewed < 240) or
            triggers['fallback3']['eligible'] is not True):
            raise ValueError('independent measured fallback eligibility')
        relations[f'{witness}/{candidate}'] = relation
    if total != 1920 or relations['exception_3_1/primary'] != 'over_200ft' or \
       relations['exception_3_2/primary'] != 'ambiguous' or \
       relations['exception_3_2/fallback3'] != 'incomplete_exit':
        raise ValueError('controlled boundary findings')
    result = {'format': 'c146314-paragraph-c1-independent-saved-audit-v1',
              'bundles': 8, 'raw_saved_rows_audited': total,
              'saved_positive': 8, 'saved_tamper_negative': 56,
              'relations': relations, 'original_native_observed': False,
              'delivery_ready': False}
    (HERE/'offline/saved-audit.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


if __name__ == '__main__':
    print(json.dumps(audit()))
