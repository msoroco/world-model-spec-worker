"""Signal timing/continuity finalization from original-run samples.

Distances refer to actual cumulative trajectory, never a planned route station.
API bits and rendered optical observations remain separate evidence.
"""
import math

def cumulative_distance(samples):
    total=0.;out=[]
    for index,sample in enumerate(samples):
        if index:total+=math.dist(samples[index-1]['position'],sample['position'])
        out.append(total)
    return out

def continuous_signal_distance(samples,onset_index):
    if onset_index<0 or onset_index>=len(samples):raise ValueError('Invalid course-change index')
    distances=cumulative_distance(samples);begin=onset_index
    # Do not cross a missing/nonactive sample; uncertainty is one original step.
    while begin>0 and samples[begin]['right_indicator'] and samples[begin-1]['right_indicator']:
        begin-=1
    return {'value_m':distances[onset_index]-distances[begin],
            'sample_window_s':[samples[begin]['time_s'],samples[onset_index]['time_s']],
            'sample_window_indices':[begin,onset_index],
            'boundary_uncertainty_m':0. if begin==0 else distances[begin]-distances[begin-1],
            'method':'actual 3D cumulative position distance through last uninterrupted right-indicator API interval; optical confirmation separate',
            'indicator_optically_confirmed':None}

def requested_signal(distance_remaining_m,requested_distance_m):
    # A controller trigger only; finalization above uses observed onset and lamps.
    return distance_remaining_m<=requested_distance_m

def mean_roi_luminance_bgra(raw,width,height,roi):
    x0,y0,x1,y1=roi
    if not (0<=x0<x1<=width and 0<=y0<y1<=height):raise ValueError('ROI outside RGB sensor')
    values=[]
    for y in range(y0,y1):
        for x in range(x0,x1):
            i=(y*width+x)*4;values.append(.0722*raw[i]+.7152*raw[i+1]+.2126*raw[i+2])
    return sum(values)/len(values)

def optical_variation(samples):
    # Report raw luminance excursion only; no fixed cutoff proves visibility or
    # excludes occlusion, exposure changes, reflection or unrelated light motion.
    if not samples:return {'confirmed':False,'reason':'no original RGB samples'}
    values=[s['roi_luminance'] for s in samples]
    return {'min_luminance':min(values),'max_luminance':max(values),
            'sample_times_s':[s['time_s'] for s in samples],
            'confirmed':None,'reason':'inspect original framed lamp ROI and cycles; luminance variation is supporting raw evidence only'}


def build_turn_road():
    from turn_surface import build_uturn
    import xml.etree.ElementTree as ET
    root=ET.fromstring(build_uturn())
    roads=root.findall('road');roads[0].set('length','160');roads[0].find('planView/geometry').set('length','160')
    import math
    roads[1].set('length',str(math.pi*15/2));arc=roads[1].find('planView/geometry');arc.set('x','160');arc.set('length',str(math.pi*15/2));arc.find('arc').set('curvature',str(1/15))
    last=roads[2].find('planView/geometry');last.set('x','175');last.set('y','15');last.set('hdg',str(math.pi/2))
    for road in roads:road.find('lanes/laneSection/right/lane/width').set('a','3.5')
    return ET.tostring(root,encoding='unicode')

def turn_route():
    approach=[(float(x),-1.75) for x in range(20,161,2)]
    arc=[(160+16.75*math.sin(t),15-16.75*math.cos(t)) for t in [i*math.pi/100 for i in range(1,51)]]
    return approach+arc+[(176.75,float(y)) for y in range(17,101,2)]
