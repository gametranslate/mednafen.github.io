"""Embedded playback regression test. Runs without foreground windows or desktop capture.
Set MEDNAFEN_PLAY_TEST_ROM to the Namco Super Wars WSC fixture supplied by the user.
"""
from pathlib import Path
import runpy
runpy.run_path(str(Path(__file__).with_name('background.spec.py')),run_name='__main__')
