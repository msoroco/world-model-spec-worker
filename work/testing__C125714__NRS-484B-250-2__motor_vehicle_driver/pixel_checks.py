"""Primary-video pixel presence check for the independent source decoder."""


def pixel_presence(frame):
    pixels = frame.pixels
    if frame.width < 1920 or frame.height < 1080 or len(pixels) != frame.width*frame.height*3:
        raise ValueError('primary frame dimensions or RGB bytes incomplete')
    # Samples from both original-view rows must vary. This is pixel presence,
    # not a claim that actors, signs or right-of-way are visible.
    stride = max(3, (len(pixels)//8192)//3*3)
    upper = pixels[:frame.width*1080*3:stride]
    lower = pixels[frame.width*1080*3::stride]
    if len(set(upper)) < 2 or len(set(lower)) < 2:
        raise ValueError('primary frame has no varying pixels in both view rows')
