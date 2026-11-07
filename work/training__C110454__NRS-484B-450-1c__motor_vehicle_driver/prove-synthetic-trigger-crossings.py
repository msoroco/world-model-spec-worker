"""Derive three parking fallback gates from saved synthetic source rows."""
import hashlib
import json
import math
from pathlib import Path

HERE=Path(__file__).resolve().parent
OUT=HERE/'fixtures/trigger-crossings'
CASES=('probe_a','probe_b')
VARIANTS=('baseline','fallback1','fallback2','fallback3')


def sha(raw):return hashlib.sha256(raw).hexdigest()
def encode(rows):return ''.join(json.dumps(row,sort_keys=True)+'\n' for row in rows).encode()


def measure(native_path,pixel_path,native_sha,pixel_sha):
    native_raw=native_path.read_bytes();pixel_raw=pixel_path.read_bytes()
    if sha(native_raw)!=native_sha or sha(pixel_raw)!=pixel_sha:
        raise ValueError('Synthetic trigger source hash changed')
    native=[json.loads(line) for line in native_raw.splitlines()]
    pixels=[json.loads(line) for line in pixel_raw.splitlines()]
    if len(native)!=480 or len(pixels)!=40:
        raise ValueError('Synthetic source frame inventory differs')
    centers=[]
    for i,row in enumerate(native):
        if row['video_frame']!=i or row['native_frame']!=1000+i or abs(row['time_s']-i/20)>1e-9:
            raise ValueError('Saved Native frame join differs')
        body=row['body_xy_m']
        if len(body)!=4 or not all(len(point)==2 and all(math.isfinite(v) for v in point) for point in body):
            raise ValueError('Saved Native body differs')
        centers.append(sum(point[1] for point in body)/4)
    for i,row in enumerate(pixels):
        if (row!={'video_frame':i,'source_kind':'synthetic_pixel_margin_mark',
                 'body_margin_px':row.get('body_margin_px')} or
            type(row['body_margin_px']) not in (int,float) or
            not math.isfinite(row['body_margin_px']) or row['body_margin_px']<0):
            raise ValueError('Synthetic pixel margin mark differs')
    metrics={'max_cross_track_error_m':round(max(abs(y+1.75) for y in centers),6),
             'mean_final_park_speed_m_s':round(sum(row['speed_m_s'] for row in native[-40:])/40,6),
             'min_vehicle_pixel_margin_px':min(row['body_margin_px'] for row in pixels)}
    decisions={'fallback1':metrics['max_cross_track_error_m']>0.45,
               'fallback2':metrics['mean_final_park_speed_m_s']>0.2,
               'fallback3':metrics['min_vehicle_pixel_margin_px']<40}
    return metrics,decisions


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    results=[]
    for case in CASES:
        base=[json.loads(line) for line in (HERE/'fixtures'/case/'native_samples.jsonl').read_text().splitlines()]
        if len(base)!=480:raise ValueError('Base fixture incomplete')
        for variant in VARIANTS:
            rows=json.loads(json.dumps(base))
            if variant=='fallback1':
                for point in rows[30]['body_xy_m']:point[1]+=0.6
            if variant=='fallback2':
                for row in rows[-40:]:row['speed_m_s']=0.3
            pixels=[{'video_frame':i,'source_kind':'synthetic_pixel_margin_mark',
                     'body_margin_px':39 if variant=='fallback3' and i==0 else 50}
                    for i in range(40)]
            native_path=OUT/f'{case}-{variant}-native.jsonl'
            pixel_path=OUT/f'{case}-{variant}-pixels.jsonl'
            native_raw=encode(rows);pixel_raw=encode(pixels)
            native_path.write_bytes(native_raw);pixel_path.write_bytes(pixel_raw)
            metrics,decisions=measure(native_path,pixel_path,sha(native_raw),sha(pixel_raw))
            if decisions!={name:name==variant for name in VARIANTS[1:]}:
                raise ValueError('Trigger crossing not isolated')
            results.append({'case':case,'variant':variant,
                            'native_sha256':sha(native_raw),'pixel_sha256':sha(pixel_raw),
                            'metrics':metrics,'decisions':decisions})
    proof={'passed':True,'cases':2,'rows':results,'source_kind':'synthetic_cpu_fixture',
           'original_native_or_pixels_observed':False,'selected':False}
    (HERE/'synthetic-trigger-crossings.json').write_text(json.dumps(proof,indent=2)+'\n')
    print(json.dumps({'passed':True,'cases':2,'crossings':len(results)}))


if __name__=='__main__':main()
