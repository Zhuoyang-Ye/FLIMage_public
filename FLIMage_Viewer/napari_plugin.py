"""
Napari reader plugin hook for FLIMage (.flim) files.
Enables opening .flim files directly in napari on both macOS and Windows.
"""

from typing import List, Tuple, Dict, Any, Optional
import numpy as np
from fast_io import FastFLIM


def napari_get_reader(path: str):
    """Determine whether the file can be read as a FLIMage file."""
    if isinstance(path, str) and (path.lower().endswith(".flim") or path.lower().endswith(".tif")):
        return flim_reader
    return None


def flim_reader(path: str) -> List[Tuple[np.ndarray, Dict[str, Any], str]]:
    """
    Read FLIMage file and return napari layer data tuples:
    [(data, meta, layer_type), ...]
    """
    flim = FastFLIM(path)
    flim.load_all()

    layers = []

    # Assemble 5D intensity and lifetime hyperstacks: [T, Z, C, Y, X]
    int_data = np.zeros(
        (flim.n_pages, flim.n_fast_z, flim.n_channels, flim.height, flim.width),
        dtype=np.float32
    )
    lt_data = np.zeros(
        (flim.n_pages, flim.n_fast_z, flim.n_channels, flim.height, flim.width),
        dtype=np.float32
    )

    for p in range(flim.n_pages):
        for z in range(flim.n_fast_z):
            for c in range(flim.n_channels):
                int_data[p, z, c] = flim.get_intensity(p, z, c)
                lt_data[p, z, c] = flim.get_lifetime_map(p, z, c)

    # Squeeze singleton dimensions if single page / single slice
    int_squeezed = np.squeeze(int_data)
    lt_squeezed = np.squeeze(lt_data)

    int_meta = {
        "name": "Intensity",
        "colormap": "gray",
        "blending": "additive",
    }
    layers.append((int_squeezed, int_meta, "image"))

    lt_meta = {
        "name": "Mean Lifetime (ns)",
        "colormap": "turbo",
        "contrast_limits": [1.6, 2.4],
        "blending": "additive",
        "opacity": 0.8,
    }
    layers.append((lt_squeezed, lt_meta, "image"))

    return layers
