"""Independent original-source comparison of backing across a crosswalk boundary."""
import importlib.util
from pathlib import Path


def _measure(root):
 spec=importlib.util.spec_from_file_location('reverse_crosswalk_for_audit',
                                          Path(__file__).with_name('crosswalk_reverse.py'))
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 return module.analyze(Path(root))


def audit(over_root, short_root):
 over,short=_measure(over_root),_measure(short_root)
 if over['sources']['crosswalk_context.json']!=short['sources']['crosswalk_context.json']:
  raise ValueError('Comparison crosswalk context differs')
 for name,digest in over['sources'].items():
  if name in ('crosswalk_context.json','reverse_history.jsonl','video_frames.jsonl'):
   continue
  if short['sources'].get(name)!=digest:
   raise ValueError('Comparison site source differs: '+name)
 for name in short['sources']:
  if name not in over['sources']:
   raise ValueError('Comparison site source differs: '+name)
 first,second=over['samples'],short['samples']
 if len(first)!=len(second):raise ValueError('Comparison frame counts differ')
 if first[0]['body_center_xy_m']!=second[0]['body_center_xy_m']:
  raise ValueError('Comparison reverse approach differs')
 if [s['native_reverse'] for s in first]!=[s['native_reverse'] for s in second]:
  raise ValueError('Comparison Native reverse schedule differs')
 if not over['backward_motion_observed'] or not short['backward_motion_observed']:
  raise ValueError('Both cases require observed backward motion')
 if not over['reverse_body_on_or_over_crosswalk']:
  raise ValueError('Over-crosswalk body entry not observed')
 if short['reverse_body_on_or_over_crosswalk']:
  raise ValueError('Short case body overlaps crosswalk')
 return {'format':'worker-reverse-crosswalk-comparison-audit',
         'crosswalk_context_sha256':over['sources']['crosswalk_context.json'],
         'over_sources':over['sources'],'short_sources':short['sources'],
         'frame_count':len(first),'physical_acceptance':'unresolved',
         'legal_conclusion':'unresolved'}
