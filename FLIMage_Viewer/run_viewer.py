#!/usr/bin/env python3
"""
Entry point to launch the FLIMage Desktop Viewer.
Usage:
    python run_viewer.py [optional_file.flim]
"""

import sys
import os

# Ensure package directory is in sys.path
viewer_dir = os.path.dirname(os.path.abspath(__file__))
if viewer_dir not in sys.path:
    sys.path.insert(0, viewer_dir)

from gui import main

if __name__ == "__main__":
    main()
