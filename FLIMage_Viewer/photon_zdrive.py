#!/usr/bin/env python3
"""
Fast Z-drive / Network-Share .photon -> .flim Converter (Windows).

Why this is much faster than opening .photon directly from Z: in FLIMage:
1. Reading/seeking inside a .photon ZIP/TAR archive directly over SMB (Z:)
   triggers thousands of slow network round-trips.
2. This tool performs ONE sequential 4 MB-buffered copy of each .photon file
   to local SSD temp storage, decodes locally via TCSPC_Decode.dll, writes the
   resulting .flim file locally, and optionally copies it back to the output
   folder (or keeps it in a local SSD cache).
3. Already-converted .flim files are skipped automatically.
"""

import argparse
import os
import platform
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import List, Optional

CHUNK_SIZE = 4 * 1024 * 1024  # 4 MB sequential SMB buffer


def _copy_sequential(src: Path, dst: Path, chunk_size: int = CHUNK_SIZE) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.name + ".part")
    with open(src, "rb") as fsrc, open(tmp, "wb") as fdst:
        shutil.copyfileobj(fsrc, fdst, length=chunk_size)
    os.replace(tmp, dst)


def find_matching_flim(photon_path: Path, output_dir: Optional[Path] = None) -> Path:
    target_dir = output_dir if output_dir is not None else photon_path.parent
    return target_dir / f"{photon_path.stem}.flim"


def convert_zdrive_photon(
    photon_path: Path,
    output_dir: Optional[Path] = None,
    dll_path: Optional[Path] = None,
    skip_existing: bool = True,
) -> Path:
    """
    Stage a .photon file from Z: (or any path) to local temp SSD, decode it to .flim
    using TCSPC_Decode.dll, and move the .flim to the target output directory.
    """
    if platform.system() != "Windows":
        raise RuntimeError(
            "Decoding .photon files requires TCSPC_Decode.dll (Windows x64 only).\n"
            "Run this script on your Windows machine to convert .photon -> .flim,\n"
            "then open the resulting .flim file in FLIMage_Viewer on macOS or Windows."
        )

    out_flim = find_matching_flim(photon_path, output_dir)
    if skip_existing and out_flim.exists() and out_flim.stat().st_size > 0:
        print(f"[skip] Already converted: {out_flim}")
        return out_flim

    python_script_dir = Path(__file__).resolve().parents[1] / "Python Script"
    if str(python_script_dir) not in sys.path:
        sys.path.insert(0, str(python_script_dir))

    from photon_to_flim import convert_photon_to_flim_native

    t0 = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="flim_zstage_") as tmpdir:
        tmp_dir = Path(tmpdir)
        local_photon = tmp_dir / photon_path.name
        local_flim = tmp_dir / f"{photon_path.stem}.flim"

        print(f"[1/3] Staging {photon_path} -> local SSD...")
        _copy_sequential(photon_path, local_photon)
        t_copy = time.perf_counter()

        print(f"[2/3] Decoding {local_photon.name} locally...")
        convert_photon_to_flim_native(local_photon, local_flim, dll_path=dll_path)
        t_dec = time.perf_counter()

        print(f"[3/3] Writing {out_flim}...")
        _copy_sequential(local_flim, out_flim)
        t_end = time.perf_counter()

    print(
        f"[done] {out_flim.name} "
        f"(stage: {t_copy - t0:.2f}s, decode: {t_dec - t_copy:.2f}s, "
        f"save: {t_end - t_dec:.2f}s, total: {t_end - t0:.2f}s)"
    )
    return out_flim


def collect_photon_files(input_path: Path) -> List[Path]:
    if input_path.is_file():
        return [input_path]
    if input_path.is_dir():
        return sorted(p for p in input_path.rglob("*.photon") if p.is_file())
    raise FileNotFoundError(f"Input path not found: {input_path}")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fast staged .photon -> .flim converter for Z-drive / network shares (Windows)."
    )
    parser.add_argument("--input", "-i", required=True, help="Path to a .photon file or folder on Z:\\.")
    parser.add_argument(
        "--output", "-o",
        help="Output folder for .flim files (default: same folder as each .photon file). "
             "Tip: pass a local SSD folder for fastest analysis.",
    )
    parser.add_argument("--dll", help="Optional explicit path to TCSPC_Decode.dll.")
    parser.add_argument(
        "--overwrite", action="store_true",
        help="Re-convert even if a matching .flim file already exists.",
    )
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    output_dir = Path(args.output) if args.output else None
    dll_path = Path(args.dll) if args.dll else None

    files = collect_photon_files(input_path)
    if not files:
        print("No .photon files found.")
        return 1

    print(f"Found {len(files)} .photon file(s).")
    failures = []
    for f in files:
        try:
            convert_zdrive_photon(
                f,
                output_dir=output_dir,
                dll_path=dll_path,
                skip_existing=not args.overwrite,
            )
        except Exception as exc:
            print(f"[error] {f}: {exc}", file=sys.stderr)
            failures.append((f, exc))

    if failures:
        print(f"\nCompleted with {len(failures)} error(s).", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
