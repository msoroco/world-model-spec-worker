"""Retain original RGB photometry in a measured projected body ROI.

This records optical evidence; it never equates a lamp API bit or a brightness
change with emitted indicator flashing. Identifying the lamp pixels and judging
visibility still requires calibration against original footage.
"""
import math

def project_body(vertices,inverse,width,height,fov_degrees):
 focal=width/(2*math.tan(math.radians(fov_degrees)/2));pixels=[]
 for point in vertices:
  local=[sum(inverse[i][j]*list(point+[1.])[j] for j in range(4)) for i in range(3)]
  if local[0]<=.01:continue
  pixels.append([width/2+focal*local[1]/local[0],height/2-focal*local[2]/local[0]])
 if not pixels:raise ValueError('Subject body behind optical camera')
 x0=max(0,int(math.floor(min(p[0] for p in pixels))));x1=min(width,int(math.ceil(max(p[0] for p in pixels))));y0=max(0,int(math.floor(min(p[1] for p in pixels))));y1=min(height,int(math.ceil(max(p[1] for p in pixels))))
 if x1<=x0 or y1<=y0:raise ValueError('Subject body outside optical image')
 return [x0,y0,x1,y1]

def photometry(raw,width,height,roi):
 if len(raw)!=width*height*4:raise ValueError('Wrong original BGRA image length')
 x0,y0,x1,y1=roi
 if not (0<=x0<x1<=width and 0<=y0<y1<=height):raise ValueError('Invalid optical ROI')
 total=0.;low=255.;high=0.;count=0
 for y in range(y0,y1):
  for x in range(x0,x1):
   k=(y*width+x)*4;b,g,r=raw[k],raw[k+1],raw[k+2];value=.2126*r+.7152*g+.0722*b;total+=value;low=min(low,value);high=max(high,value);count+=1
 return dict(mean_luminance=total/count,min_luminance=low,max_luminance=high,pixel_count=count,method='original BGRA-derived Rec709-weighted RGB values; uncalibrated camera intensity, not physical radiance')

class BodyOpticalTap:
 def __init__(self,stream,camera,ego,width,height,history):self.stream=stream;self.camera=camera;self.ego=ego;self.width=width;self.height=height;self.history=history
 @property
 def closed(self):return self.stream.closed
 def close(self):return self.stream.close()
 def write(self,data):
  world=self.ego.get_world();snapshot=world.get_snapshot();ct=self.camera.get_transform();et=self.ego.get_transform();vertices=[[p.x,p.y,p.z] for p in self.ego.bounding_box.get_world_vertices(et)];fov=float(self.camera.attributes.get('fov',90));roi=project_body(vertices,ct.get_inverse_matrix(),self.width,self.height,fov)
  self.history.append(dict(carla_frame=snapshot.frame,time_s=snapshot.timestamp.elapsed_seconds,body_roi_pixels=roi,body_vertices_m=vertices,camera_inverse_matrix=ct.get_inverse_matrix(),camera_fov_degrees=fov,photometry=photometry(data,self.width,self.height,roi),lamp_bits=int(self.ego.get_light_state()),interpretation='body ROI is not a calibrated lamp mask; retain original footage for emitted-light review'))
  return self.stream.write(data)
