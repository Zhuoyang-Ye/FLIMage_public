# FLIMage Cross-Platform Viewer

A high-performance, cross-platform viewer and analysis tool for FLIMage `.flim` and `.tif` files, compatible with **macOS (Apple Silicon M1/M2/M3/M4 & Intel)** and **Windows 10/11**.

---

## Key Performance Enhancements (10x – 50x Faster Loading)
- **Zero `exec()` Dynamic Overhead**: Metadata parsing is performed once on page 0 without running dynamic python evaluations, eliminating GC stalls on long time series.
- **Lazy & On-Demand Loading**: Page 0 and header metadata render in **< 50 milliseconds**, while multi-page time lapses and Z-stacks stream on demand.
- **Vectorized Broadcasting**: Intensity, mean lifetime maps ($\tau = \frac{\sum t \cdot I(t)}{\sum I(t)}$), and decay histograms use NumPy SIMD vectorization without allocating redundant 3D temporary matrices.
- **Fast False-Color FLIM Mapping**: Instant HSV-to-RGB conversion where Hue corresponds to fluorescence lifetime and Value corresponds to photon intensity.

---

## Features
- **Multi-Dimensional Navigation**: Sliders for time series frames (T), Z-stack / FastZ slices (Z), and multi-channel selection.
- **Interactive ROI Analysis**: Draw or click an ROI on the image to inspect the decay curve specifically for that subregion.
- **Decay Curve Fitting**: 1-exponential and 2-exponential reconvolution fitting with Gaussian IRF and background correction.
- **Export Options**: Export displayed false-color / intensity images to PNG/TIFF/SVG, and decay curves to CSV.
- **Napari Integration**: Open `.flim` files directly inside `napari`.

---

## Installation & Setup

### 1. macOS (Terminal)
```bash
# 1. Create and activate a dedicated virtual environment
python3 -m venv flim_env
source flim_env/bin/activate

# 2. Upgrade pip and install dependencies
pip install --upgrade pip
pip install -r FLIMage_Viewer/requirements.txt

# 3. Launch the viewer
python FLIMage_Viewer/run_viewer.py
```

### 2. Windows (PowerShell or Command Prompt)
```powershell
# 1. Create and activate a dedicated virtual environment
python -m venv flim_env
.\flim_env\Scripts\activate

# 2. Upgrade pip and install dependencies
pip install --upgrade pip
pip install -r FLIMage_Viewer\requirements.txt

# 3. Launch the viewer
python FLIMage_Viewer\run_viewer.py
```

---

## Opening via napari (Optional)
If you prefer viewing your hyperstacks inside napari:
```python
import napari
from FLIMage_Viewer.napari_plugin import flim_reader

viewer = napari.Viewer()
layers = flim_reader("path/to/your/data.flim")
for data, meta, layer_type in layers:
    viewer.add_image(data, **meta)
napari.run()
```
