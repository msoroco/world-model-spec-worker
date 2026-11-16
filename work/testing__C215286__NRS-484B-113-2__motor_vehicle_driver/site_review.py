"""Byte-bound site context for a proposed residence-district crosswalk.

The returned check is source completeness, not a legal district or marked
crosswalk determination. Original camera pixels require separate review.
"""
import hashlib
from pathlib import Path
from shapely.geometry import Polygon


def _source(root,row,label):
 if not isinstance(row,dict) or not row.get('path') or not row.get('sha256'):
  raise ValueError('Missing '+label+' source binding')
 rel=Path(row['path'])
 if rel.is_absolute() or '..' in rel.parts:raise ValueError('Unsafe '+label+' source path')
 path=Path(root)/rel
 if not path.is_file():raise ValueError('Missing '+label+' source file')
 digest=hashlib.sha256(path.read_bytes()).hexdigest()
 if digest!=row['sha256']:raise ValueError('Stale '+label+' source hash')
 return {'path':str(rel),'sha256':digest}


def validate(packet,root,*,native_map_id,road_id,crosswalk_id):
 if not isinstance(packet,dict):raise ValueError('Site packet must be an object')
 if (packet.get('native_map_id'),packet.get('road_id'),packet.get('crosswalk_id'))!=(native_map_id,road_id,crosswalk_id):
  raise ValueError('Site packet road/crosswalk identity differs')
 if packet.get('district_kind')!='residence' or not packet.get('district_review_basis'):
  raise ValueError('Residence-district review declaration required')
 if not packet.get('crosswalk_review_basis') or not packet.get('reviewer'):
  raise ValueError('Crosswalk and reviewer basis required')
 crossing=Polygon(packet.get('crosswalk_polygon_xy_m',[]))
 roadway=Polygon(packet.get('roadway_polygon_xy_m',[]))
 if not crossing.is_valid or crossing.area<=0 or not roadway.is_valid or roadway.area<=0:
  raise ValueError('Invalid reviewed site polygons')
 if crossing.intersection(roadway).area<=0:
  raise ValueError('Crosswalk does not intersect selected roadway')
 sources={key:_source(root,packet.get(key+'_source'),key) for key in
          ('district','crosswalk_geometry','crosswalk_marking')}
 return {'format':'worker-reverse-crosswalk-site-source-check',
         'native_map_id':native_map_id,'road_id':road_id,'crosswalk_id':crosswalk_id,
         'sources':sources,'district_status':'independent review required',
         'marked_crosswalk_visibility':'unverified'}
