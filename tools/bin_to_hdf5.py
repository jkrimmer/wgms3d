#!/usr/bin/env python3
"""
wgms3d_to_hdf5.py

Convert wgms3d binary field files (hr-*.bin / hz-*.bin) in a directory
into a single HDF5 file, with r and z coordinate arrays stored as
root-level attributes.

Usage:
    python wgms3d_to_hdf5.py <directory> [--output OUTPUT]

The directory must contain:
  - hr-<N>.bin and hz-<N>.bin files (one pair per mode index N)
  OR
  - sc-<N>.bin files (scalar modes, one per mode index N)
  - r.txt   - radial coordinate array (one value per line)
  - z.txt   - axial  coordinate array (one value per line)

Binary file format (discovered empirically)
-------------------------------------------
Each .bin file begins with a 2-float64 header:
  [n_eff_real, n_eff_imag]   - complex effective index of the mode
Followed by the field data in Fortran (column-major) order:
  2*len_r * len_z float64 values, interleaved real/imag along the r axis.

Output HDF5 structure
---------------------
/Hr/Mode <N+1>   - complex dataset, shape (len_z, len_r)
                   attribute "n_eff" - complex effective index (float64[2])
/Hz/Mode <N+1>   - complex dataset, shape (len_z, len_r)
                   attribute "n_eff" - complex effective index (float64[2])

Root attributes
---------------
r   - 1-D complex128 array read from r.txt
z   - 1-D complex128 array read from z.txt
"""

import argparse
import re
import os
import sys
from pathlib import Path

import numpy as np
import h5py


# ---------------------------------------------------------------------------
# Binary reader (mirrors wgms3d_read_bin_data.m)
# ---------------------------------------------------------------------------

def read_bin_field(path: Path, r: np.ndarray, z: np.ndarray) -> tuple[complex, np.ndarray]:
    """
    Read a wgms3d binary field file and return (n_eff, field).

    File layout
    -----------
    [0]   beta_real  - float64  ┐ complex propagation constant
    [1]   beta_imag  - float64  ┘
    [2:]  field data  - 2*len_r*len_z float64 values in Fortran order:
          interleaved real/imag pairs along the r axis, column-major over z.

    The field is reshaped to (2*len_r, len_z) then transposed to
    (len_z, len_r), matching MATLAB's  data(real,:)' + i*data(imag,:)'.

    Parameters
    ----------
    path : Path       - path to the .bin file.
    r    : np.ndarray - radial coordinate vector (1-D).
    z    : np.ndarray - axial  coordinate vector (1-D).

    Returns
    -------
    beta   : complex  - propagation constant from the file header.
    field  : np.ndarray, dtype=complex128, shape=(len_z, len_r)
    """
    len_r = len(r)
    len_z = len(z)

    raw = np.fromfile(path, dtype=np.float64)

    # Header: 2 float64 values encoding the complex effective index.
    HEADER = 2
    expected_total = HEADER + 2 * len_r * len_z
    if raw.size != expected_total:
        raise ValueError(
            f"{path.name}: expected {expected_total} float64 values "
            f"({HEADER} header + 2*{len_r}*{len_z} field), got {raw.size}."
        )

    beta = complex(raw[0], raw[1])
    body  = raw[HEADER:]

    # Reshape to (2*len_r, len_z) in Fortran (column-major) order,
    # matching MATLAB's fread( f, [2*length(x), length(y)], 'double' ).
    data = body.reshape((2 * len_r, len_z), order='F')

    real_part = data[0::2, :]   # rows 0,2,4,... (0-based) → real
    imag_part = data[1::2, :]   # rows 1,3,5,... (0-based) → imaginary

    # Transpose: MATLAB's  data(real,:)'  gives shape (len_z, len_r)
    # field = real_part.T + 1j * imag_part.T
    field = real_part + 1j * imag_part
    return beta, field


# ---------------------------------------------------------------------------
# Directory scanning helpers
# ---------------------------------------------------------------------------

_SC_PATTERN = re.compile(r'^sc-(\d+)\.bin$', re.IGNORECASE)
_HR_PATTERN = re.compile(r'^hr-(\d+)\.bin$', re.IGNORECASE)
_HP_PATTERN = re.compile(r'^hp-(\d+)\.bin$', re.IGNORECASE)
_HZ_PATTERN = re.compile(r'^hz-(\d+)\.bin$', re.IGNORECASE)
_ER_PATTERN = re.compile(r'^er-(\d+)\.bin$', re.IGNORECASE)
_EP_PATTERN = re.compile(r'^ep-(\d+)\.bin$', re.IGNORECASE)
_EZ_PATTERN = re.compile(r'^ez-(\d+)\.bin$', re.IGNORECASE)


def collect_bin_files(directory: Path):
    """
    Scan *directory* and collect scalar/vector component files.

    Behavior:
        - If any sc-*.bin files exist, only scalar files are used.
        - Otherwise hr-*.bin and hz-*.bin are required and must index-match.
        - Optional hp/er/ep/ez files are included only for indices that match
            the required hr/hz mode set.

    Returns
    -------
    tuple[str, dict[str, dict[int, Path]], list[int]]
        (mode, component_files, sorted_indices)
        mode is either "scalar" or "vector".
        component_files maps component name (e.g. "hr") to index->Path.
        sorted_indices is the mode index list used for conversion.
    """
    sc_files: dict[int, Path] = {}
    hr_files: dict[int, Path] = {}
    hp_files: dict[int, Path] = {}
    hz_files: dict[int, Path] = {}
    er_files: dict[int, Path] = {}
    ep_files: dict[int, Path] = {}
    ez_files: dict[int, Path] = {}

    for f in directory.iterdir():
        if not f.is_file():
            continue
        # Scalar fields
        m = _SC_PATTERN.match(f.name)
        if m:
            sc_files[int(m.group(1))] = f
            continue
        # Vector field components 
        # Hr
        m = _HR_PATTERN.match(f.name)
        if m:
            hr_files[int(m.group(1))] = f
            continue
        # Hp
        m = _HP_PATTERN.match(f.name)
        if m:
            hp_files[int(m.group(1))] = f
            continue
        # Hz
        m = _HZ_PATTERN.match(f.name)
        if m:
            hz_files[int(m.group(1))] = f
            continue
        # Er
        m = _ER_PATTERN.match(f.name)
        if m:
            er_files[int(m.group(1))] = f
            continue
        # Ep
        m = _EP_PATTERN.match(f.name)
        if m:
            ep_files[int(m.group(1))] = f
            continue
        # Ez
        m = _EZ_PATTERN.match(f.name)
        if m:
            ez_files[int(m.group(1))] = f

    if sc_files:
        sc_indices = sorted(sc_files)
        print(f"Found scalar mode(s): {len(sc_files)}  indices {sc_indices}")
        return "scalar", {"sc": sc_files}, sc_indices

    if not hr_files:
        raise ValueError("No hr-*.bin files found in the directory.")
    if not hz_files:
        raise ValueError("No hz-*.bin files found in the directory.")

    # hp, er, ep, ez files are optional; hr and hz pairs are required.
    hr_indices = set(hr_files)
    hz_indices = set(hz_files)

    if hr_indices != hz_indices:
        only_hr = sorted(hr_indices - hz_indices)
        only_hz = sorted(hz_indices - hr_indices)
        msg_parts = []
        if only_hr:
            msg_parts.append(f"hr-only indices: {only_hr}")
        if only_hz:
            msg_parts.append(f"hz-only indices: {only_hz}")
        raise ValueError(
            "Mismatch between hr and hz file indices. " + "; ".join(msg_parts)
        )

    required_indices = sorted(hr_indices)
    required_set = set(required_indices)

    def _matching_optional(component: str, files: dict[int, Path]) -> dict[int, Path]:
        if not files:
            return {}
        extra = sorted(set(files) - required_set)
        if extra:
            print(
                f"Warning: ignoring {component}-only indices without hr/hz pair: {extra}",
                file=sys.stderr,
            )
        return {idx: path for idx, path in files.items() if idx in required_set}

    component_files = {
        "hr": hr_files,
        "hz": hz_files,
    }

    hp_matching = _matching_optional("hp", hp_files)
    er_matching = _matching_optional("er", er_files)
    ep_matching = _matching_optional("ep", ep_files)
    ez_matching = _matching_optional("ez", ez_files)

    if hp_matching:
        component_files["hp"] = hp_matching
    if er_matching:
        component_files["er"] = er_matching
    if ep_matching:
        component_files["ep"] = ep_matching
    if ez_matching:
        component_files["ez"] = ez_matching

    print(f"Found vector mode(s): {len(required_indices)}  indices {required_indices}")
    optional_present = [k for k in ("hp", "er", "ep", "ez") if k in component_files]
    if optional_present:
        print(f"Including optional components: {', '.join(optional_present)}")

    return "vector", component_files, required_indices


# ---------------------------------------------------------------------------
# Coordinate loaders
# ---------------------------------------------------------------------------

def load_coord(path: Path, name: str) -> np.ndarray:
    """Load a whitespace/newline-delimited float array from a text file."""
    try:
        arr = np.loadtxt(path).view(dtype=np.complex128)
    except Exception as exc:
        raise ValueError(f"Could not read {name} from {path}: {exc}") from exc

    arr = np.atleast_1d(arr.ravel())
    if arr.size == 0:
        raise ValueError(f"{name} array in {path} is empty.")
    print(f"Loaded {name}: {arr.size} values  [{arr[0]:.6g} … {arr[-1]:.6g}]")
    return arr


# ---------------------------------------------------------------------------
# Main conversion routine
# ---------------------------------------------------------------------------

def convert(directory: Path, output_path: Path, delete_inputs: bool = False) -> None:
    # ── 1. Validate directory ────────────────────────────────────────────
    if not directory.exists():
        print(f"Error: directory '{directory}' does not exist.", file=sys.stderr)
        sys.exit(1)
    if not directory.is_dir():
        print(f"Error: '{directory}' is not a directory.", file=sys.stderr)
        sys.exit(1)

    print(f"Scanning: {directory.resolve()}")

    # ── 2. Collect bin files ─────────────────────────────────────────────
    try:
        mode_kind, component_files, sorted_indices = collect_bin_files(directory)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    # ── 3. Load coordinate arrays ────────────────────────────────────────
    r_path = directory / "r.txt"
    z_path = directory / "z.txt"

    for p, label in [(r_path, "r.txt"), (z_path, "z.txt")]:
        if not p.exists():
            print(f"Error: required file '{label}' not found in {directory}.", file=sys.stderr)
            sys.exit(1)

    try:
        r = load_coord(r_path, "r")
        z = load_coord(z_path, "z")
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    # ── 4. Write HDF5 ────────────────────────────────────────────────────
    print(f"\nWriting HDF5: {output_path}")

    with h5py.File(output_path, "w") as hf:
        # Root attributes
        hf.attrs["r"] = r
        hf.attrs["z"] = z

        if mode_kind == "scalar":
            hdf5_groups = {"sc": hf.create_group("Scalar")}
        else:
            hdf5_groups = {
                "hr": hf.create_group("Hr"),
                "hz": hf.create_group("Hz"),
            }
            if "hp" in component_files:
                hdf5_groups["hp"] = hf.create_group("Hp")
            if "er" in component_files:
                hdf5_groups["er"] = hf.create_group("Er")
            if "ep" in component_files:
                hdf5_groups["ep"] = hf.create_group("Ep")
            if "ez" in component_files:
                hdf5_groups["ez"] = hf.create_group("Ez")

        for idx in sorted_indices:
            mode_label = f"Mode {idx + 1}"

            print(f"  Processing {mode_label}  (file index {idx}) …", end="", flush=True)

            try:
                component_data = {}
                for component, files in component_files.items():
                    if idx not in files:
                        continue
                    n_eff, field_data = read_bin_field(files[idx], r, z)
                    component_data[component] = (n_eff, field_data)
            except (ValueError, OSError) as exc:
                print(f"\nError reading mode {idx}: {exc}", file=sys.stderr)
                sys.exit(1)

            # Store complex field data; attach beta as a per-dataset attribute.
            # (HDF5 has no native complex type; h5py uses a compound dtype
            #  that most readers handle transparently as complex128.)
            for component, (beta, data) in component_data.items():
                ds = hdf5_groups[component].create_dataset(mode_label, data=data)
                ds.attrs["beta"] = [beta.real, beta.imag]

            # Prefer hr for vector status line, otherwise fall back to scalar.
            status_component = "hr" if "hr" in component_data else "sc"
            status_beta, status_data = component_data[status_component]
            print(
                f" shape={status_data.shape}, "
                f" beta={status_beta.real:.10f}{status_beta.imag:+.3e}j"
            )

    print(f"\nDone. Output: {output_path.resolve()}")

    if delete_inputs:
        print("Deleting input files …")
        for files in component_files.values():
            for path in files.values():
                try:
                    path.unlink()
                except OSError as exc:
                    print(f"Warning: could not delete {path}: {exc}", file=sys.stderr)
        for coord_path in [r_path, z_path]:
            try:
                coord_path.unlink()
            except OSError as exc:
                print(f"Warning: could not delete {coord_path}: {exc}", file=sys.stderr)
        print("Input files deleted.")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Convert wgms3d binary field files (hr-*.bin / hz-*.bin) to HDF5.\n\n"
            "The target directory must also contain r.txt and z.txt."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--directory", "-d",
        type=Path,
        default=os.getcwd(),
        help="Path to the folder containing the .bin, r.txt and z.txt files.",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=Path(os.getcwd(), "modes.h5"),
        help=(
            "Path for the output HDF5 file. "
            "Defaults to <directory>/modes.h5"
        ),
    )
    parser.add_argument(
        "--delete-inputs",
        action="store_true",
        help="Delete the input .bin and .txt files after conversion.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    directory: Path = args.directory.expanduser().resolve()
    output_path: Path = (
        args.output.expanduser().resolve()
        if args.output is not None
        else directory / "modes.h5"
    )
    convert(directory, output_path, args.delete_inputs)


if __name__ == "__main__":
    main()