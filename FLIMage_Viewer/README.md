# FLIMage Python Viewer

A fast, lightweight Python GUI and Z-drive helper for viewing and analyzing FLIMage `.flim` and `.photon` files on Windows.

---

## Key Performance Enhancements
- **Fast Z-Drive `.photon` Staging**: [`photon_zdrive.py`](photon_zdrive.py) copies `.photon` archives sequentially in 4 MB chunks to local SSD temp storage before decoding with `TCSPC_Decode.dll`, avoiding slow SMB random seeks.
- **Lazy `.flim` Loading**: Only Page 0 metadata and pixels are read on open; timestamps and frames load on demand.
- **Local SSD Cache**: Optional **"Cache locally (Z-drive)"** toggle copies remote `.flim` files once to local temp SSD and reuses them.
- **Vectorized FLIM Math**: Intensity, mean lifetime maps, and RGB overlays use 1D NumPy broadcasting.

---

## Setup & Launch (Windows Conda)

```powershell
# 1. Navigate to the repository
cd path\to\FLIMage_public

# 2. Create and activate the conda environment
conda env create -f FLIMage_Viewer\environment.yml
conda activate flimage_env

# 3. Launch the GUI
python FLIMage_Viewer\run_viewer.py
```

Or pass a `.flim` / `.photon` file directly:
```powershell
python FLIMage_Viewer\run_viewer.py Z:\path\to\data.flim
```

---

## Batch Convert `.photon` → `.flim` from Z-Drive

```powershell
# Convert a folder on Z: (skips already-converted files)
python FLIMage_Viewer\photon_zdrive.py --input Z:\path\to\experiment

# Or write .flim outputs directly to a local SSD folder
python FLIMage_Viewer\photon_zdrive.py --input Z:\path\to\experiment --output D:\flim_cache
```
