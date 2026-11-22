"""Decoded four-view blank and truncated source rejection."""
import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('c10808_pixels',ROOT/'pixel_checks.py')
pixels=importlib.util.module_from_spec(spec);spec.loader.exec_module(pixels)


class PixelChecksTests(unittest.TestCase):
    def test_four_views_and_missing_view(self):
        width,height=3840,1800
        data=bytearray(width*height*3)
        for x,y,w,h in pixels.VIEWS:
            offset=((y+h//2)*width+x+w//2)*3
            data[offset]=150
        frame=SimpleNamespace(width=width,height=height,pixels=data)
        pixels.check(frame)
        x,y,w,h=pixels.VIEWS[2]
        data[((y+h//2)*width+x+w//2)*3]=0
        with self.assertRaisesRegex(ValueError,'view is blank: 2'):
            pixels.check(frame)

    def test_truncated_frame(self):
        with self.assertRaisesRegex(ValueError,'truncated'):
            pixels.check(SimpleNamespace(width=3840,height=1800,pixels=b''))


if __name__=='__main__':unittest.main()
