
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

Vendored PETSc optimization flags, i.e.
- `WGMS3D_PETSC_COPTFLAGS`
- `WGMS3D_PETSC_CXXOPTFLAGS`
- `WGMS3D_PETSC_FOPTFLAGS`
are set to `-O3` by default.


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
