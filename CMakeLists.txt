cmake_minimum_required(VERSION 3.20)
project(wgms3d VERSION 2.0 LANGUAGES C CXX Fortran)

include(GNUInstallDirs)
include(FetchContent)
include(ExternalProject)
include(CTest)

set(CMAKE_CXX_STANDARD 11)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

set(WGMS3D_BOOST_VERSION "1.91.0" CACHE STRING "Boost version to vendor when WGMS3D_VENDOR_BOOST=ON")
set(WGMS3D_OPENBLAS_VERSION "0.3.33" CACHE STRING "OpenBLAS version to vendor when WGMS3D_VENDOR_BLAS_LAPACK=ON")
set(WGMS3D_SUPERLU_VERSION "7.0.1" CACHE STRING "SuperLU version to vendor when WGMS3D_VENDOR_SUPERLU=ON")
set(WGMS3D_ARPACK_VERSION "3.9.1" CACHE STRING "ARPACK-NG version to vendor when WGMS3D_VENDOR_ARPACK=ON")
set(WGMS3D_PETSC_VERSION "3.25.0" CACHE STRING "PETSc version to vendor when WGMS3D_VENDOR_PETSC_SLEPC=ON")
set(WGMS3D_SLEPC_VERSION "3.25.0" CACHE STRING "SLEPc version to vendor when WGMS3D_VENDOR_PETSC_SLEPC=ON")
string(REPLACE "." "_" WGMS3D_BOOST_VERSION_UNDERSCORE "${WGMS3D_BOOST_VERSION}")

option(WGMS3D_WITH_SUPERLU_ARPACK "Build SuperLU/ARPACK solver backend" ON)
option(WGMS3D_WITH_PETSC_SLEPC "Build PETSc/SLEPc solver backend" OFF)
option(WGMS3D_WITH_MPI "Build with MPI support" ${WGMS3D_WITH_PETSC_SLEPC})

if(WGMS3D_WITH_PETSC_SLEPC)
  if(WGMS3D_WITH_SUPERLU_ARPACK)
    message(STATUS "WGMS3D_WITH_PETSC_SLEPC=ON: disabling WGMS3D_WITH_SUPERLU_ARPACK automatically.")
  endif()
  set(WGMS3D_WITH_SUPERLU_ARPACK OFF CACHE BOOL "Build SuperLU/ARPACK solver backend" FORCE)
endif()

option(WGMS3D_VENDOR_BOOST "Fetch Boost headers into the build tree" ON)
option(WGMS3D_VENDOR_SUPERLU "Fetch/build SuperLU in the build tree" ON)
option(WGMS3D_VENDOR_ARPACK "Fetch/build ARPACK in the build tree" ON)
option(WGMS3D_VENDOR_BLAS_LAPACK "Fetch/build OpenBLAS as BLAS/LAPACK provider" OFF)
option(WGMS3D_VENDOR_PETSC_SLEPC "Fetch/build PETSc/SLEPc in the build tree" OFF)
option(WGMS3D_VENDOR_PETSC_COMPLEX "When vendoring PETSc/SLEPc, build PETSc with complex scalars" ON)
option(WGMS3D_WITH_CUDA "Enable CUDA acceleration via PETSc/SLEPc CUDA backend (requires CUDA toolkit)" OFF)
set(WGMS3D_CUDA_ARCH "" CACHE STRING "CUDA architecture for vendored PETSc CUDA build (e.g. sm_80); empty = auto-detect")
set(WGMS3D_PETSC_COPTFLAGS "-O3" CACHE STRING "Optimization flags for vendored PETSc C builds")
set(WGMS3D_PETSC_CXXOPTFLAGS "-O3" CACHE STRING "Optimization flags for vendored PETSc C++ builds")
set(WGMS3D_PETSC_FOPTFLAGS "-O3" CACHE STRING "Optimization flags for vendored PETSc Fortran builds")

if(WGMS3D_WITH_SUPERLU_ARPACK AND WGMS3D_WITH_PETSC_SLEPC)
  message(FATAL_ERROR "SuperLU/ARPACK and PETSc/SLEPc are mutually exclusive.")
endif()

if(NOT WGMS3D_WITH_SUPERLU_ARPACK AND NOT WGMS3D_WITH_PETSC_SLEPC)
  message(FATAL_ERROR "No solver selected. Enable one of WGMS3D_WITH_SUPERLU_ARPACK or WGMS3D_WITH_PETSC_SLEPC.")
endif()

if(WGMS3D_WITH_PETSC_SLEPC AND NOT WGMS3D_WITH_MPI AND NOT WGMS3D_VENDOR_PETSC_SLEPC)
  message(FATAL_ERROR "PETSc/SLEPc backend without vendoring requires WGMS3D_WITH_MPI=ON.")
endif()

if((WGMS3D_WITH_PETSC_SLEPC AND WGMS3D_VENDOR_PETSC_SLEPC) OR BUILD_TESTING)
  find_package(Python3 REQUIRED COMPONENTS Interpreter)
endif()

set(common_sources
  src/main.cc
  src/wgms3d.cc
  src/diffops.cc
  src/mgp.cc
  src/bezier.cc
)

if(WGMS3D_WITH_SUPERLU_ARPACK)
  list(APPEND common_sources src/solver_superlu_arpack.cc)
endif()

if(WGMS3D_WITH_PETSC_SLEPC)
  list(APPEND common_sources src/solver_slepc.cc)
endif()

if(WGMS3D_VENDOR_BOOST)
  FetchContent_Declare(
    boost_headers
    URL https://archives.boost.io/release/${WGMS3D_BOOST_VERSION}/source/boost_${WGMS3D_BOOST_VERSION_UNDERSCORE}.tar.gz
    DOWNLOAD_EXTRACT_TIMESTAMP TRUE
  )
  FetchContent_MakeAvailable(boost_headers)
  set(BOOST_INCLUDE_DIR "${boost_headers_SOURCE_DIR}")
else()
  find_path(BOOST_INCLUDE_DIR boost/throw_exception.hpp)
endif()

if(NOT BOOST_INCLUDE_DIR)
  message(FATAL_ERROR "Boost headers not found. Set WGMS3D_VENDOR_BOOST=ON or provide BOOST_INCLUDE_DIR.")
endif()

if(WGMS3D_VENDOR_BLAS_LAPACK)
  FetchContent_Declare(
    openblas
    URL https://github.com/OpenMathLib/OpenBLAS/archive/refs/tags/v${WGMS3D_OPENBLAS_VERSION}.tar.gz
    DOWNLOAD_EXTRACT_TIMESTAMP TRUE
  )
  set(BUILD_TESTING OFF CACHE BOOL "" FORCE)
  set(BUILD_SHARED_LIBS OFF CACHE BOOL "" FORCE)
  set(USE_OPENMP OFF CACHE BOOL "" FORCE)
  FetchContent_MakeAvailable(openblas)
  set(BLAS_LIBRARIES openblas)
  set(LAPACK_LIBRARIES openblas)
else()
  find_package(BLAS REQUIRED)
  find_package(LAPACK REQUIRED)
endif()

set(BLAS_FOR_VENDOR ${BLAS_LIBRARIES})
set(LAPACK_FOR_VENDOR ${LAPACK_LIBRARIES})
if(BLAS_FOR_VENDOR)
  list(GET BLAS_FOR_VENDOR 0 BLAS_FOR_VENDOR)
endif()
if(LAPACK_FOR_VENDOR)
  list(GET LAPACK_FOR_VENDOR 0 LAPACK_FOR_VENDOR)
endif()

set(extra_include_dirs)
set(extra_link_libraries)
set(WGMS3D_COMPILE_WITH_MPI OFF)
set(WGMS3D_COMPILE_WITH_PETSC OFF)
set(WGMS3D_COMPILE_WITH_SLEPC OFF)

set(WGMS3D_USE_SYSTEM_MPI OFF)
set(WGMS3D_VENDOR_PETSC_NEEDS_MPI OFF)
if(WGMS3D_WITH_PETSC_SLEPC AND WGMS3D_VENDOR_PETSC_SLEPC)
  set(WGMS3D_VENDOR_PETSC_NEEDS_MPI ON)
endif()

if(WGMS3D_WITH_MPI OR WGMS3D_VENDOR_PETSC_NEEDS_MPI)
  if(WGMS3D_VENDOR_PETSC_NEEDS_MPI)
    find_package(MPI QUIET COMPONENTS C CXX Fortran)
    if(MPI_CXX_FOUND)
      set(WGMS3D_USE_SYSTEM_MPI ON)
      if(WGMS3D_WITH_MPI)
        list(APPEND extra_link_libraries MPI::MPI_CXX)
        set(WGMS3D_COMPILE_WITH_MPI ON)
      endif()
    elseif(WGMS3D_WITH_MPI)
      message(STATUS "System MPI not found. Vendored PETSc/SLEPc will download MPICH so PETSc can build with MUMPS.")
    else()
      message(STATUS "Vendored PETSc/SLEPc will download MPICH so PETSc can build with MUMPS.")
    endif()
  else()
    find_package(MPI REQUIRED COMPONENTS C CXX Fortran)
    set(WGMS3D_USE_SYSTEM_MPI ON)
    list(APPEND extra_link_libraries MPI::MPI_CXX)
    set(WGMS3D_COMPILE_WITH_MPI ON)
  endif()
endif()

if(WGMS3D_WITH_SUPERLU_ARPACK)
  if(WGMS3D_VENDOR_SUPERLU)
    set(SUPERLU_INSTALL_DIR ${CMAKE_BINARY_DIR}/_deps/superlu)
    file(MAKE_DIRECTORY ${SUPERLU_INSTALL_DIR}/include)
    file(MAKE_DIRECTORY ${SUPERLU_INSTALL_DIR}/lib)
    ExternalProject_Add(superlu_ep
      URL https://github.com/xiaoyeli/superlu/archive/refs/tags/v${WGMS3D_SUPERLU_VERSION}.tar.gz
      PREFIX ${CMAKE_BINARY_DIR}/_deps/superlu_ep
      INSTALL_DIR ${SUPERLU_INSTALL_DIR}
      DOWNLOAD_EXTRACT_TIMESTAMP TRUE
      CMAKE_ARGS
        -DCMAKE_INSTALL_PREFIX=<INSTALL_DIR>
        -DCMAKE_INSTALL_LIBDIR=lib
        -DBUILD_SHARED_LIBS=OFF
        -Denable_internal_blaslib=OFF
      CMAKE_CACHE_ARGS
        -DTPL_BLAS_LIBRARIES:STRING=${BLAS_FOR_VENDOR}
    )
    add_library(superlu_vendor STATIC IMPORTED GLOBAL)
    set_target_properties(superlu_vendor PROPERTIES
      IMPORTED_LOCATION ${SUPERLU_INSTALL_DIR}/lib/libsuperlu.a
      INTERFACE_INCLUDE_DIRECTORIES ${SUPERLU_INSTALL_DIR}/include
    )
    add_dependencies(superlu_vendor superlu_ep)
    set(SUPERLU_INCLUDE_DIR ${SUPERLU_INSTALL_DIR}/include)
    set(SUPERLU_LIBRARIES superlu_vendor)
  else()
    find_path(SUPERLU_INCLUDE_DIR slu_ddefs.h)
    find_library(SUPERLU_LIBRARY superlu)
    if(NOT SUPERLU_INCLUDE_DIR OR NOT SUPERLU_LIBRARY)
      message(FATAL_ERROR "SuperLU not found. Set WGMS3D_VENDOR_SUPERLU=ON or provide SUPERLU_INCLUDE_DIR/SUPERLU_LIBRARY.")
    endif()
    set(SUPERLU_LIBRARIES ${SUPERLU_LIBRARY})
  endif()

  if(WGMS3D_VENDOR_ARPACK)
    set(ARPACK_INSTALL_DIR ${CMAKE_BINARY_DIR}/_deps/arpack)
    file(MAKE_DIRECTORY ${ARPACK_INSTALL_DIR}/lib)
    ExternalProject_Add(arpack_ep
      URL https://github.com/opencollab/arpack-ng/archive/refs/tags/${WGMS3D_ARPACK_VERSION}.tar.gz
      PREFIX ${CMAKE_BINARY_DIR}/_deps/arpack_ep
      INSTALL_DIR ${ARPACK_INSTALL_DIR}
      DOWNLOAD_EXTRACT_TIMESTAMP TRUE
      CMAKE_ARGS
        -DCMAKE_INSTALL_PREFIX=<INSTALL_DIR>
        -DCMAKE_INSTALL_LIBDIR=lib
        -DBUILD_SHARED_LIBS=OFF
        -DICB=OFF
        -DMPI=OFF
        -DEXAMPLES=OFF
        -DTESTS=OFF
      CMAKE_CACHE_ARGS
        -DBLAS_LIBRARIES:STRING=${BLAS_FOR_VENDOR}
        -DLAPACK_LIBRARIES:STRING=${LAPACK_FOR_VENDOR}
    )
    add_library(arpack_vendor STATIC IMPORTED GLOBAL)
    set_target_properties(arpack_vendor PROPERTIES
      IMPORTED_LOCATION ${ARPACK_INSTALL_DIR}/lib/libarpack.a
    )
    add_dependencies(arpack_vendor arpack_ep)
    set(ARPACK_LIBRARIES arpack_vendor)
  else()
    find_library(ARPACK_LIBRARY arpack)
    if(NOT ARPACK_LIBRARY)
      message(FATAL_ERROR "ARPACK not found. Set WGMS3D_VENDOR_ARPACK=ON or provide ARPACK_LIBRARY.")
    endif()
    set(ARPACK_LIBRARIES ${ARPACK_LIBRARY})
  endif()

  list(APPEND extra_include_dirs ${SUPERLU_INCLUDE_DIR})
  list(APPEND extra_link_libraries ${SUPERLU_LIBRARIES} ${ARPACK_LIBRARIES})
  if(CMAKE_Fortran_IMPLICIT_LINK_LIBRARIES)
    list(APPEND extra_link_libraries ${CMAKE_Fortran_IMPLICIT_LINK_LIBRARIES})
  endif()
endif()

if(WGMS3D_WITH_PETSC_SLEPC)
  if(WGMS3D_VENDOR_PETSC_SLEPC)
    set(PETSC_INSTALL_DIR ${CMAKE_BINARY_DIR}/_deps/petsc)
    set(SLEPC_INSTALL_DIR ${CMAKE_BINARY_DIR}/_deps/slepc)
    file(MAKE_DIRECTORY
      ${PETSC_INSTALL_DIR}/include
      ${PETSC_INSTALL_DIR}/lib
      ${SLEPC_INSTALL_DIR}/include
      ${SLEPC_INSTALL_DIR}/lib
    )

    set(_petsc_cc ${CMAKE_C_COMPILER})
    set(_petsc_cxx ${CMAKE_CXX_COMPILER})
    set(_petsc_fc ${CMAKE_Fortran_COMPILER})
    # ScaLAPACK's BLACS tools use legacy C function declarations that break under C23.
    # GCC 15 defaults to gnu23, so force a compatible C dialect for vendored PETSc deps.
    set(_petsc_cflags -std=gnu17)
    set(_petsc_with_mpi 1)
    set(_petsc_scalar_type real)
    set(_petsc_mpi_args)
    set(_petsc_clean_env ${CMAKE_COMMAND} -E env --unset=MAKEFLAGS)
    set(_petsc_mumps_args
      --download-mumps=1
      --download-scalapack=1
      --download-scalapack-cmake-arguments=-DCMAKE_C_STANDARD=17
      --download-metis=1
      --download-parmetis=1
    )
    set(_petsc_blaslapack_args --download-f2cblaslapack=1)
    if(WGMS3D_USE_SYSTEM_MPI)
      if(MPI_C_COMPILER)
        set(_petsc_cc ${MPI_C_COMPILER})
      endif()
      if(MPI_CXX_COMPILER)
        set(_petsc_cxx ${MPI_CXX_COMPILER})
      endif()
      if(MPI_Fortran_COMPILER)
        set(_petsc_fc ${MPI_Fortran_COMPILER})
      endif()
    else()
      set(_petsc_mpi_args --download-mpich=1)
    endif()

    if(WGMS3D_VENDOR_PETSC_COMPLEX)
      set(_petsc_scalar_type complex)
    endif()

    set(_petsc_cuda_args)
    if(WGMS3D_WITH_CUDA)
      list(APPEND _petsc_cuda_args --with-cuda=1)
      if(WGMS3D_CUDA_ARCH)
        list(APPEND _petsc_cuda_args --with-cuda-arch=${WGMS3D_CUDA_ARCH})
      endif()
    endif()

    ExternalProject_Add(petsc_ep
      URL https://github.com/petsc/petsc/archive/refs/tags/v${WGMS3D_PETSC_VERSION}.tar.gz
      PREFIX ${CMAKE_BINARY_DIR}/_deps/petsc_ep
      INSTALL_DIR ${PETSC_INSTALL_DIR}
      DOWNLOAD_EXTRACT_TIMESTAMP TRUE
      BUILD_IN_SOURCE TRUE
        CONFIGURE_COMMAND ${_petsc_clean_env} ${Python3_EXECUTABLE} <SOURCE_DIR>/configure
          CC=${_petsc_cc}
          CXX=${_petsc_cxx}
          FC=${_petsc_fc}
          CFLAGS+=${_petsc_cflags}
          COPTFLAGS=${WGMS3D_PETSC_COPTFLAGS}
          CXXOPTFLAGS=${WGMS3D_PETSC_CXXOPTFLAGS}
          FOPTFLAGS=${WGMS3D_PETSC_FOPTFLAGS}
          --prefix=<INSTALL_DIR>
          --with-debugging=0
          --with-shared-libraries=1
          --with-x=0
          --with-mpi=${_petsc_with_mpi}
          --with-scalar-type=${_petsc_scalar_type}
          --with-cxx-dialect=C++11
            ${_petsc_mpi_args}
            ${_petsc_mumps_args}
          ${_petsc_blaslapack_args}
          ${_petsc_cuda_args}
      BUILD_COMMAND ${_petsc_clean_env} ${CMAKE_MAKE_PROGRAM}
      INSTALL_COMMAND ${_petsc_clean_env} ${CMAKE_MAKE_PROGRAM} install
      BUILD_BYPRODUCTS ${PETSC_INSTALL_DIR}/lib/libpetsc${CMAKE_SHARED_LIBRARY_SUFFIX}
    )

    ExternalProject_Add(slepc_ep
      URL https://github.com/slepc/slepc/archive/refs/tags/v${WGMS3D_SLEPC_VERSION}.tar.gz
      PREFIX ${CMAKE_BINARY_DIR}/_deps/slepc_ep
      INSTALL_DIR ${SLEPC_INSTALL_DIR}
      DOWNLOAD_EXTRACT_TIMESTAMP TRUE
      BUILD_IN_SOURCE TRUE
      DEPENDS petsc_ep
      CONFIGURE_COMMAND ${CMAKE_COMMAND} -E env --unset=MAKEFLAGS
        PETSC_DIR=${PETSC_INSTALL_DIR}
        PETSC_ARCH=
        ${Python3_EXECUTABLE} <SOURCE_DIR>/configure
          --prefix=<INSTALL_DIR>
      BUILD_COMMAND ${CMAKE_COMMAND} -E env --unset=MAKEFLAGS
        SLEPC_DIR=<SOURCE_DIR>
        PETSC_DIR=${PETSC_INSTALL_DIR}
        PETSC_ARCH=
        ${CMAKE_MAKE_PROGRAM}
      INSTALL_COMMAND ${CMAKE_COMMAND} -E env --unset=MAKEFLAGS
        SLEPC_DIR=<SOURCE_DIR>
        PETSC_DIR=${PETSC_INSTALL_DIR}
        PETSC_ARCH=
        ${CMAKE_MAKE_PROGRAM} install
      BUILD_BYPRODUCTS ${SLEPC_INSTALL_DIR}/lib/libslepc${CMAKE_SHARED_LIBRARY_SUFFIX}
    )

    add_library(petsc_vendor SHARED IMPORTED GLOBAL)
    set_target_properties(petsc_vendor PROPERTIES
      IMPORTED_LOCATION ${PETSC_INSTALL_DIR}/lib/libpetsc${CMAKE_SHARED_LIBRARY_SUFFIX}
      INTERFACE_INCLUDE_DIRECTORIES ${PETSC_INSTALL_DIR}/include
    )
    add_dependencies(petsc_vendor petsc_ep)

    if(NOT WGMS3D_USE_SYSTEM_MPI)
      add_library(petsc_vendor_mpi SHARED IMPORTED GLOBAL)
      set_target_properties(petsc_vendor_mpi PROPERTIES
        IMPORTED_LOCATION ${PETSC_INSTALL_DIR}/lib/libmpi${CMAKE_SHARED_LIBRARY_SUFFIX}
      )
      add_dependencies(petsc_vendor_mpi petsc_ep)
      set_property(TARGET petsc_vendor APPEND PROPERTY
        INTERFACE_LINK_LIBRARIES petsc_vendor_mpi
      )
    endif()

    add_library(slepc_vendor SHARED IMPORTED GLOBAL)
    set_target_properties(slepc_vendor PROPERTIES
      IMPORTED_LOCATION ${SLEPC_INSTALL_DIR}/lib/libslepc${CMAKE_SHARED_LIBRARY_SUFFIX}
      INTERFACE_INCLUDE_DIRECTORIES ${SLEPC_INSTALL_DIR}/include
    )
    add_dependencies(slepc_vendor slepc_ep)

    set(PETSC_INCLUDE_DIR ${PETSC_INSTALL_DIR}/include)
    set(SLEPC_INCLUDE_DIR ${SLEPC_INSTALL_DIR}/include)
    set(PETSC_LIBRARY petsc_vendor)
    set(SLEPC_LIBRARY slepc_vendor)
  else()
    find_path(PETSC_INCLUDE_DIR
      petsc.h
      HINTS $ENV{PETSC_DIR}
      PATH_SUFFIXES include include/petsc
    )
    find_library(PETSC_LIBRARY
      petsc
      HINTS $ENV{PETSC_DIR}
      PATH_SUFFIXES lib lib64 $ENV{PETSC_ARCH}/lib
    )
    find_path(SLEPC_INCLUDE_DIR
      slepceps.h
      HINTS $ENV{SLEPC_DIR}
      PATH_SUFFIXES include
    )
    find_library(SLEPC_LIBRARY
      slepc
      HINTS $ENV{SLEPC_DIR}
      PATH_SUFFIXES lib lib64 $ENV{PETSC_ARCH}/lib
    )

    if(NOT PETSC_INCLUDE_DIR OR NOT PETSC_LIBRARY)
      message(FATAL_ERROR "PETSc not found. Set WGMS3D_VENDOR_PETSC_SLEPC=ON or provide PETSC_DIR/PETSC_ARCH hints.")
    endif()
    if(NOT SLEPC_INCLUDE_DIR OR NOT SLEPC_LIBRARY)
      message(FATAL_ERROR "SLEPc not found. Set WGMS3D_VENDOR_PETSC_SLEPC=ON or provide SLEPC_DIR/PETSC_ARCH hints.")
    endif()
  endif()

  list(APPEND extra_include_dirs ${PETSC_INCLUDE_DIR} ${SLEPC_INCLUDE_DIR})
  list(APPEND extra_link_libraries ${SLEPC_LIBRARY} ${PETSC_LIBRARY})
  set(WGMS3D_COMPILE_WITH_PETSC ON)
  set(WGMS3D_COMPILE_WITH_SLEPC ON)
endif()

add_executable(wgms3d ${common_sources})
target_include_directories(wgms3d PRIVATE
  include
  ${BOOST_INCLUDE_DIR}
  ${extra_include_dirs}
)
target_compile_definitions(wgms3d PRIVATE
  WGMS3D_VERSION_STR="${PROJECT_VERSION}"
  $<$<BOOL:${WGMS3D_COMPILE_WITH_MPI}>:WGMS3D_WITH_MPI>
  $<$<BOOL:${WGMS3D_COMPILE_WITH_PETSC}>:WGMS3D_WITH_PETSC>
  $<$<BOOL:${WGMS3D_COMPILE_WITH_SLEPC}>:WGMS3D_WITH_SLEPC>
  $<$<BOOL:${WGMS3D_WITH_CUDA}>:WGMS3D_WITH_CUDA>
)
target_compile_options(wgms3d PRIVATE -Wall -pedantic)
if(CMAKE_Fortran_IMPLICIT_LINK_DIRECTORIES)
  target_link_directories(wgms3d PRIVATE ${CMAKE_Fortran_IMPLICIT_LINK_DIRECTORIES})
endif()
target_link_libraries(wgms3d PRIVATE
  ${extra_link_libraries}
  ${LAPACK_LIBRARIES}
  ${BLAS_LIBRARIES}
)

if(BUILD_TESTING)
  add_test(NAME wgms3d_help_usage
    COMMAND $<TARGET_FILE:wgms3d> -h
  )
  set_tests_properties(wgms3d_help_usage PROPERTIES
    PASS_REGULAR_EXPRESSION "Usage:"
  )

  add_test(NAME wgms3d_noargs_usage
    COMMAND $<TARGET_FILE:wgms3d>
  )
  set_tests_properties(wgms3d_noargs_usage PROPERTIES
    PASS_REGULAR_EXPRESSION "Usage:"
  )

  set(_fiber_convergence_workdir "${CMAKE_CURRENT_SOURCE_DIR}/tests/fiber_convergence")
  set(_fiber_convergence_script "${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/check_fiber_convergence.py")
  set(_fiber_convergence_grid "-U;0:120:12.99101;-V;0:120:12.99101")
  string(JOIN "|" _fiber_convergence_grid_joined ${_fiber_convergence_grid})
  set(_fiber_convergence_rel_tol "5e-4")

  function(add_fiber_convergence_test test_name)
    set(options)
    set(oneValueArgs EXPECTED)
    set(multiValueArgs CASE_ARGS)
    cmake_parse_arguments(FIBER "${options}" "${oneValueArgs}" "${multiValueArgs}" ${ARGN})
    string(JOIN "|" fiber_case_args_joined ${FIBER_CASE_ARGS})
    string(REPLACE ";" "|" fiber_expected_joined "${FIBER_EXPECTED}")

    add_test(NAME ${test_name}
      COMMAND ${Python3_EXECUTABLE} ${_fiber_convergence_script}
        --test-name ${test_name}
        --wgms3d-bin $<TARGET_FILE:wgms3d>
        --working-directory ${_fiber_convergence_workdir}
        --case-args=${fiber_case_args_joined}
        --grid-args=${_fiber_convergence_grid_joined}
        --expected-neff=${fiber_expected_joined}
        --rel-tol ${_fiber_convergence_rel_tol}
    )
  endfunction()

  add_fiber_convergence_test(wgms3d_fiber_case13_1
    CASE_ARGS -l 10 -g fiber.mgp -n 2
    EXPECTED "2.161722239740193;2.102237229347229"
  )
  add_fiber_convergence_test(wgms3d_fiber_case13_2
    CASE_ARGS -l 10 -g fiber.mgp -n 2 -M s
    EXPECTED "2.351757217372069;1.843555913442746"
  )
  add_fiber_convergence_test(wgms3d_fiber_case13_3
    CASE_ARGS -l 10 -g fiber.mgp -n 2 -M w
    EXPECTED "2.351757217372069;1.843555913442746"
  )
  add_fiber_convergence_test(wgms3d_fiber_case13_4
    CASE_ARGS -l 10 -g fiber.mgp -n 4 -M w -M s
    EXPECTED "2.102237229347229;2.082244850080460"
  )
endif()

install(TARGETS wgms3d RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR})
install(DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/doc/ DESTINATION ${CMAKE_INSTALL_DATADIR}/wgms3d/doc)
install(DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/matlab/ DESTINATION ${CMAKE_INSTALL_DATADIR}/wgms3d/matlab)
install(DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/tests/ DESTINATION ${CMAKE_INSTALL_DATADIR}/wgms3d/tests)