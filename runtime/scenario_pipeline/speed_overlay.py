"""Render measured speeds joined to original camera frames, never commands."""
import hashlib
import math
from pathlib import Path
from batch_pipeline.speed_policy import MPH_MPS


def measured_samples(trace, mapping, first, end):
    if len(trace)!=len(mapping):raise ValueError('Speed/video frame count mismatch')
    selected=[]
    for i in range(first,end):
        t,m=trace[i],mapping[i]
        if t['frame']!=m['carla_frame'] or abs(t['time_s']-m['time_s'])>1e-6:
            raise ValueError('Speed/video original frame join mismatch')
        if not math.isfinite(t['speed_mps']):raise ValueError('Nonfinite measured speed')
        selected.append(t['speed_mps'])
    return selected


def timestamp(seconds):
    ticks=round(seconds*100)
    return '%d:%02d:%02d.%02d'%(ticks//360000,ticks//6000%60,ticks//100%60,ticks%100)


def write_overlay(path, trace, mapping, first, end, width, height, y, fps=20, size=14):
    values=measured_samples(trace,mapping,first,end)
    content='''[Script Info]
ScriptType: v4.00+
PlayResX: %d
PlayResY: %d
WrapStyle: 2
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Speed,Liberation Sans,%d,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,1,0,7,8,8,0,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''%(width,height,size)
    for i,v in enumerate(values):
        label='Measured ego speed: %.3f mph | %.3f km/h | %.4f m/s'%(v/MPH_MPS,v*3.6,v)
        content+='Dialogue: 0,%s,%s,Speed,,0,0,0,,{\\an7\\pos(8,%d)}%s\n'%(timestamp(i/fps),timestamp((i+1)/fps),y,label)
    Path(path).write_text(content)
    return hashlib.sha256(content.encode()).hexdigest()


def ass_filter(path):
    value=str(Path(path).resolve()).replace('\\','\\\\').replace(':','\\:').replace("'","'\\''")
    return "ass=filename='%s'"%value
