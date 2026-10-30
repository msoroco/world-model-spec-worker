"""Check saved lamp flashing samples against original API activation and frames."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw

def read(path):return json.loads(path.read_text())
def stream(path):return [json.loads(s) for s in path.read_text().splitlines()]

def verify(attempt):
 states=stream(attempt/'ego_turn_indicator.jsonl');mapping=stream(attempt/'video_frames.jsonl')
 first=next(i for i,r in enumerate(states) if r['value'].get('reported_device_state',r['value'].get('state'))=='left')
 images=sorted((attempt/'raw').glob('*.png'))
 if len(images)!=len(mapping) or len(states)!=len(mapping):raise ValueError('Original image/indicator/frame count mismatch')
 start=first+20;indices=list(range(start,min(start+40,len(images))))
 crop=(400,364,418,385);means=[];samples=[];canvas=Image.new('RGB',(8*125,5*168),'black');draw=ImageDraw.Draw(canvas)
 for k,i in enumerate(indices):
  if states[i]['time_s']!=mapping[i]['time_s']:raise ValueError('Image and indicator timestamps differ')
  with Image.open(images[i]) as image:
   if image.size!=(960,540):raise ValueError('Lamp ROI requires the recorded 960x540 chase configuration')
   pixels=np.asarray(image.crop(crop).convert('RGB')).astype(float);mean=float(np.mean(pixels@np.array([.2126,.7152,.0722])))
   tile=image.crop((385,340,435,400)).resize((125,180))
  means.append(mean);x=k%8*125;y=k//8*168;canvas.paste(tile,(x,y));draw.text((x+2,y+2),str(i),fill='white')
  samples.append({'source_video_frame':i,'frame_mapping':mapping[i],'image':str(images[i]),'image_sha256':hashlib.sha256(images[i].read_bytes()).hexdigest(),'indicator_api':states[i],'lamp_roi_luminance':mean})
 threshold=(min(means)+max(means))/2;phases=[v>threshold for v in means];changes=sum(a!=b for a,b in zip(phases,phases[1:]));contrast=max(means)-min(means)
 baseline=[]
 for i in range(max(0,first-40),first):
  with Image.open(images[i]) as image:
   baseline.append(float(np.mean(np.asarray(image.crop(crop).convert('RGB')).astype(float)@np.array([.2126,.7152,.0722]))))
 noise=float(np.std(baseline));minimum_contrast=max(2.,6*noise)
 if contrast<minimum_contrast or changes<2:raise ValueError('Flashing phases not established from saved lamp ROI: contrast %.3f, required %.3f, transitions %d'%(contrast,minimum_contrast,changes))
 sheet=attempt/'indicator_visibility_samples.png';canvas.save(str(sheet))
 record={'status':'sampled_flashing_visible','scope':'Recorded lamp phase variation with synchronized sole-left API state; sampled emitted-light evidence, not a perception claim','contact_sheet':str(sheet),'contact_sheet_source_video_frames':[indices[0],indices[-1]],'crop_box_pixels':list(crop),'luminance_range':[min(means),max(means)],'observed_phase_transitions':changes,'baseline_luminance_noise_std':noise,'minimum_contrast':minimum_contrast,'contrast_policy':'At least two 8-bit luminance counts and six times measured off-state noise; not a signal-distance allowance','samples':samples}
 receipt=attempt/'rendered_indicator_review.json'
 if receipt.exists():
  history=attempt/'report_history';history.mkdir(exist_ok=True);original=receipt.read_bytes();archived=history/('rendered_indicator_review-'+hashlib.sha256(original).hexdigest()+'.json')
  if not archived.exists():archived.write_bytes(original)
 receipt.write_text(json.dumps(record,indent=2)+'\n');return record

def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args();index=read(args.output/'delivery_index.json');records=[]
 for cell in index['cells']:
  for case in cell['cases']:
   if '-413-2-' not in case['case_id']:continue
   evidence=verify(Path(case['execution']));records.append({'case_id':case['case_id'],'status':evidence['status'],'contrast':evidence['luminance_range'][1]-evidence['luminance_range'][0]});print(json.dumps(records[-1]),flush=True)
 (args.output/'rendered_indicator_audit.json').write_text(json.dumps({'passed':True,'cases':records},indent=2)+'\n')
if __name__=='__main__':main()
