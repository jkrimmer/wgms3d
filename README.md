
# wgms3d

wgms3d is a full-vectorial finite-difference mode solver.

Version: 2.0

Copyright (C) 2005-2014 Michael Krause <m.krause@tu-harburg.de>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

For user documentation, see: `doc/index.html`


## Build and Installation (CMake)

wgms3d uses CMake as the supported build/install system.

### Quick Start
1. Configure:
```bash
cmake -B build
```
2. Build:
```bash
cmake --build build -j
```
3. Install:
```bash
cmake --install build
```
4. Run:
```bash
./build/wgms3d
```
5. Quick functionality check:
```bash
ctest --test-dir build
```

### Custom Install Prefix
```bash
cmake -B build -DCMAKE_INSTALL_PREFIX="$HOME/.local"
cmake --build build -j
cmake --install build
```

### Main CMake Options

- `WGMS3D_WITH_SUPERLU_ARPACK=ON|OFF`
- `WGMS3D_WITH_PETSC_SLEPC=ON|OFF`
- `WGMS3D_WITH_MPI=ON|OFF`
- `WGMS3D_VENDOR_BOOST=ON|OFF`
- `WGMS3D_VENDOR_SUPERLU=ON|OFF`
- `WGMS3D_VENDOR_ARPACK=ON|OFF`
- `WGMS3D_VENDOR_BLAS_LAPACK=ON|OFF`
- `WGMS3D_VENDOR_PETSC_SLEPC=ON|OFF`
- `WGMS3D_VENDOR_PETSC_COMPLEX=ON|OFF` (default: `ON`)
- `WGMS3D_PETSC_DIRECT_SOLVER=MUMPS|SUPERLU_DIST|UMFPACK` (default: `MUMPS`) — direct sparse solver used by vendored PETSc
- `WGMS3D_WITH_CUDA=ON|OFF` (default: `OFF`) — enable CUDA backend (PETSc/SLEPc only)
- `WGMS3D_CUDA_ARCH=<sm_XX>` — pin CUDA architecture for vendored PETSc build (e.g. `sm_80`)

Current backend behavior:
- We build with SuperLU/ARPACK by default.
- If `WGMS3D_WITH_PETSC_SLEPC=ON`, `WGMS3D_WITH_SUPERLU_ARPACK` is disabled automatically.
- `WGMS3D_WITH_MPI` defaults to the PETSc backend setting.


### PETSc/SLEPc backend

System PETSc/SLEPc (untested):
```bash
PETSC_DIR=/path/to/petsc SLEPC_DIR=/path/to/slepc \
cmake -B build -DWGMS3D_WITH_PETSC_SLEPC=ON
cmake --build build -j
```

Vendored PETSc/SLEPc:
```bash
cmake -B build \
    -DWGMS3D_WITH_PETSC_SLEPC=ON \
    -DWGMS3D_VENDOR_PETSC_SLEPC=ON
cmake --build build -j
```

When `WGMS3D_VENDOR_PETSC_SLEPC=ON` and no system MPI is available, MPICH is
fetched automatically for the vendored PETSc build.

#### Direct sparse solver (`WGMS3D_PETSC_DIRECT_SOLVER`)

The shift-and-invert step inside SLEPc requires a direct LU factorization.
Three choices are available via `WGMS3D_PETSC_DIRECT_SOLVER` (only relevant
when `WGMS3D_VENDOR_PETSC_SLEPC=ON`; with a system PETSc the solver embedded
in that build is used instead):

| Value | Library downloaded by PETSc | MPI-parallel LU? | Notes |
|---|---|---|---|
| `MUMPS` (default) | MUMPS + ScaLAPACK + METIS + ParMETIS | yes | Best choice for multi-process runs |
| `SUPERLU_DIST` | SuperLU_DIST + METIS + ParMETIS | yes | Alternative parallel direct solver |
| `UMFPACK` | SuiteSparse (UMFPACK) + METIS | no (sequential) | Not suitable for MPI |

Example — build with UMFPACK as the factorization backend:
```bash
cmake -B build \
    -DWGMS3D_WITH_PETSC_SLEPC=ON \
    -DWGMS3D_VENDOR_PETSC_SLEPC=ON \
    -DWGMS3D_PETSC_DIRECT_SOLVER=UMFPACK
cmake --build build -j
```

Vendored PETSc optimization flags, i.e.
- `WGMS3D_PETSC_COPTFLAGS`
- `WGMS3D_PETSC_CXXOPTFLAGS`
- `WGMS3D_PETSC_FOPTFLAGS`
are set to `-O3` by default.


### CUDA acceleration (PETSc/SLEPc backend only)

wgms3d can offload the sparse eigensolver to an NVIDIA GPU via PETSc's CUDA
backend.  Two operations might benefit:

| Operation | GPU path |
|-----------|----------|
| Sparse matrix–vector products (outer Krylov loop) | cuSPARSE (`MATAIJCUSPARSE`) |
| Shift-and-invert LU factorization + triangular solves | cuSPARSE direct solver (`MATSOLVERCUSPARSE`, single-process only) |

Keeping both operations on the GPU is critical for performance.  If only the
SpMV runs on GPU while the LU solve remains on CPU (as with MUMPS), the
frequent host-device transfers dominate and erase any benefit.

GPU acceleration is **opt-in at runtime** via the `--cuda` flag.  The same
binary runs on CPU by default and switches to GPU when `--cuda` is passed.

**`MATSOLVERCUSPARSE` vs. MUMPS**: PETSc's `MATSOLVERCUSPARSE` is automatically
used for the LU factorization and triangular solves when running with `--cuda`
on a single MPI process (the typical use case), keeping the entire solve on
the GPU — no extra flags required.
For multi-process MPI runs `MATSOLVERCUSPARSE` is sequential-only, so MUMPS
is used as a fallback (LU on CPU, SpMV on GPU).

A CUDA toolkit installation is required.

**Vendored PETSc/SLEPc with CUDA (recommended):**
```bash
cmake -B build \
    -DWGMS3D_WITH_PETSC_SLEPC=ON \
    -DWGMS3D_VENDOR_PETSC_SLEPC=ON \
    -DWGMS3D_WITH_CUDA=ON
cmake --build build -j
```

To target a specific GPU architecture and avoid the auto-detection overhead,
pass `WGMS3D_CUDA_ARCH` (use the `sm_XX` identifier matching your GPU, e.g.
`sm_80` for Ampere, `sm_89` for Ada Lovelace):
```bash
cmake -B build \
    -DWGMS3D_WITH_PETSC_SLEPC=ON \
    -DWGMS3D_VENDOR_PETSC_SLEPC=ON \
    -DWGMS3D_WITH_CUDA=ON \
    -DWGMS3D_CUDA_ARCH=sm_80
cmake --build build -j
```

**System PETSc/SLEPc built with CUDA:**

If your system PETSc was already compiled with CUDA support, pass
`-DWGMS3D_WITH_CUDA=ON` so that wgms3d enables the `--cuda` runtime flag:
```bash
PETSC_DIR=/path/to/petsc SLEPC_DIR=/path/to/slepc \
cmake -B build \
    -DWGMS3D_WITH_PETSC_SLEPC=ON \
    -DWGMS3D_WITH_CUDA=ON
cmake --build build -j
```

**Using the GPU at runtime:**

```bash
# CPU solve (default):
./build/wgms3d -l 1.55 -g geometry.mgp -U ... -V ... -n 4

# GPU solve:
./build/wgms3d --cuda -l 1.55 -g geometry.mgp -U ... -V ... -n 4
```

Passing `--cuda` to a build not compiled with `-DWGMS3D_WITH_CUDA=ON` prints
an error and exits.

**Verifying CUDA is active:**

wgms3d prints the solver in use:
```
Solver used for factorization: : cusparse.
```

**Runtime tuning:**

Most solver settings are exposed to the command line via `EPSSetFromOptions`
(which cascades through ST → KSP → PC). Useful flags:

```bash
# Profile where time is spent:
./build/wgms3d --cuda -log_view [other options...]

# Increase Krylov subspace size (more memory, fewer restarts, sometimes faster):
./build/wgms3d --cuda -eps_ncv 60 [other options...]

# Increase tolerance (lower precision, sometimes faster):
./build/wgms3d --cuda -eps_tol 1e-8 [other options...]
```

Note: 
- `-st_pc_factor_mat_solver_type` can be used to manuelly set the solver, e.g., to use MUMPS (CPU) for the LU-factorization with GPU-based eigensolving.
- `-st_ksp_type gmres -st_pc_type jacobi` enables using iterative factorization


## Authors and Credits

wgms3d was written by Michael Krause <m.krause@tu-harburg.de>.

Thanks to Henry Wu <henrywuuts@gmail.com> for initial experiments on
parallelizing wgms3d (pwgms3d-1.3), which inspired modularization of the
older code base and the solver_slepc.cc module.

wgms3d also incorporates code by:

- Steven G. Johnson <stevenj@alum.mit.edu>
    (autoconf macros for LAPACK and BLAS detection;
     original license: GPL with autoconf exception)

- The lib2geom team,
    Marco Cecchetti <mrcekets at gmail.com>,
    Michael G. Sloan <mgsloan@gmail.com> and others
    (geometry.h, bezier.cc:
     some geometry and Bezier code;
     original license: LGPL-2.1 or MPL-1.1)

- Per Vognsen <vognsen@frost.slimy.com>
    (bezier.cc:
     polynomial root finder;
     original license: "This software is free for any use.")


## TODO

- Improve parallelism: matrix setup and derived-field computation are currently
    performed in the main process only.
- Run systematic scaling tests of the parallel version.
- Add automatic unit tests to the build process.


## Developer Notes

Some notes on the design and internal data structures of wgms3d (some notes
might no longer apply to current code):

- Two-dimensional arrays for user-grid data (field/refractive-index data) are
    stored in Fortran order.
- The finite-difference matrix is set up as complex doubles first.
- The solver is formulated in terms of transverse H-field components (Hrho,
    Hz); other fields are derived afterward.
- The grid is extended by ghost points first; zero-known unknowns are then
    eliminated from the system.
- The class implementation historically assumed one-shot usage per geometry
    setup.
- Most code paths were prepared for larger stencils than the standard 9-point
    stencil.
