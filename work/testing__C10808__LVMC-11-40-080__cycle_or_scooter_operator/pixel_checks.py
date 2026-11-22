"""Check decoded RGB presence in all four C10808 source views.

This detects blank or missing views. It does not recognize a sign, bicycle,
mounted rider or pedestrian duty; those require independent visual review.
"""

VIEWS=((960,0,1920,1080),(0,1080,1280,720),
       (1280,1080,1280,720),(2560,1080,1280,720))


def check(frame):
    if (frame.width,frame.height)!=(3840,1800):
        raise ValueError('C10808 composed source dimensions differ')
    if len(frame.pixels)!=frame.width*frame.height*3:
        raise ValueError('C10808 decoded RGB frame is truncated')
    stride=frame.width*3
    for view,(x,y,width,height) in enumerate(VIEWS):
        visible=False
        for row in range(1,8):
            yy=y+height*row//8
            for column in range(1,8):
                xx=x+width*column//8
                offset=yy*stride+xx*3
                if any(frame.pixels[offset:offset+3]):
                    visible=True;break
            if visible:break
        if not visible:
            raise ValueError('C10808 decoded source view is blank: '+str(view))
