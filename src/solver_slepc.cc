
/*
  This file is part of wgms3d, a full-vectorial finite-difference
  mode solver.

  This file implements interfaces to the eigensolvers in PETSc /
  SLEPc.

  Copyright (C) 2013-2014 Michael Krause <m.krause@tu-harburg.de>

  This program is free software: you can redistribute it and/or modify
  it under the terms of the GNU General Public License as published by
  the Free Software Foundation, either version 3 of the License, or
  (at your option) any later version.

  This program is distributed in the hope that it will be useful,
  but WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
  GNU General Public License for more details.

  You should have received a copy of the GNU General Public License
  along with this program.  If not, see <http://www.gnu.org/licenses/>.
*/

#include <type_traits>
#include <stdexcept>
#include <cstring>
#include <memory>
#include <algorithm>
#include <vector>
#define PETSC_CLANGUAGE_CXX 1

#include <boost/throw_exception.hpp>
#include <petsc.h>

#include <slepceps.h>
#include <petscsys.h>
#include <petscdmda.h>
#include <petscksp.h>
#include <petscerror.h>


#include "solver.h"
#include "make_unique.h"
#include "complex_functions.h"



namespace {

    // This class wraps all PETSc object allocations.
    class SlepcSolverResult : public ISolverResult
    {
    private:
	const int n;
	int rank;
	Mat mat;
	EPS eps;
	Vec xr, xi;
	Vec local_vector;

	// don't throw here; called by destructor
	void freePetscMembers ()
	{
	    VecDestroy(&local_vector);
	    VecDestroy(&xi);
	    VecDestroy(&xr);
	    EPSDestroy(&eps);
	    MatDestroy(&mat);
	}

	void scatterToLocalVector (Vec v)
	{
 	    VecScatter ctx;
	    PetscErrorCode ierr;
	    ierr = VecScatterCreateToZero(v, &ctx, &local_vector); CHKERRXX(ierr);
	    ierr = VecScatterBegin(ctx, v, local_vector, INSERT_VALUES, SCATTER_FORWARD); CHKERRXX(ierr);
	    ierr = VecScatterEnd(ctx, v, local_vector, INSERT_VALUES, SCATTER_FORWARD); CHKERRXX(ierr);
	    ierr = VecScatterDestroy(&ctx); CHKERRXX(ierr);
	}

	std::complex<double> maybeMergeRealImaginary (double &re, double &im) const
	{
	    return std::complex<double>(re, im);
	}

	// "If PETSc is configured with complex scalars the eigenvalue
	// is stored directly in eigr (eigi is set to zero)."
	std::complex<double> maybeMergeRealImaginary (std::complex<double> &re, std::complex<double> &) const
	{
	    return re;
	}

	// For real-scalar version of PETSc, need to separately copy
	// the imaginary part of the eigenvector into the result.
	template <typename Scalar>
	void copyImaginaryPart (
	    std::vector<std::complex<double>> & result,
	    typename std::enable_if< std::is_same<Scalar, double>::value >::type * = 0
	    )
	{
	    scatterToLocalVector(xi);
	    if(rank == 0) {
		Scalar *pLocalData;
		PetscErrorCode ierr;
		ierr = VecGetArray(local_vector, &pLocalData); CHKERRXX(ierr);
		for(int j = 0; j < n; ++j) {
		    result[j].imag(pLocalData[j]);
		}
		ierr = VecRestoreArray(local_vector, &pLocalData); CHKERRXX(ierr);
	    }
	}

	template <typename Scalar>
	void copyImaginaryPart (
	    std::vector<std::complex<double>> &,
	    typename std::enable_if< std::is_same<Scalar, std::complex<double>>::value >::type * = 0
	    )
	{
	    // don't need to do anything when PETSc was compiled for
	    // complex scalars.
	}

    public:

	SlepcSolverResult (
	    std::unique_ptr< sparse_matrix<std::complex<double>> > matrix,
	    bool is_matrix_real,
	    double sigma,
	    int num_eigenvalues,
	    bool use_cuda
	    )
	    : n(matrix->n),
	      mat(nullptr), eps(nullptr), xr(nullptr), xi(nullptr), local_vector(nullptr)
	{
	    SlepcInitialize(NULL,NULL,(char *)0,NULL);
		MPI_Comm_rank(MPI_COMM_WORLD, &rank);
	    int mpi_size = 1;
	    MPI_Comm_size(PETSC_COMM_WORLD, &mpi_size);

	    if(rank == 0 && is_matrix_real && std::is_same< PetscScalar, std::complex<double> >::value)
	    {
		std::cout << "Note: system matrix is real, but PETSc is complex;" << std::endl;
		std::cout << "  consider compiling against real PETSc for reduced memory use." << std::endl;
	    }

	    PetscErrorCode ierr;

	    ierr = MatCreate(PETSC_COMM_WORLD, &mat); CHKERRXX(ierr);
	    ierr = MatSetSizes(mat, PETSC_DECIDE, PETSC_DECIDE, n, n); CHKERRXX(ierr);
#ifdef WGMS3D_WITH_CUDA
	    if(use_cuda) {
			// Use MATAIJCUSPARSE so PETSc offloads sparse matrix-vector
			// products to the GPU during Krylov iterations.
			ierr = MatSetType(mat, MATAIJCUSPARSE); CHKERRXX(ierr);
	    } else {
			ierr = MatSetType(mat, MATAIJ); CHKERRXX(ierr);
	    }
#else
	    ierr = MatSetType(mat, MATAIJ); CHKERRXX(ierr);
#endif
	    ierr = MatSetFromOptions(mat); CHKERRXX(ierr);
	    ierr = MatSetUp(mat); CHKERRXX(ierr);

	    ierr = MatSeqAIJSetPreallocation(mat, 18, nullptr); CHKERRXX(ierr);
	    ierr = MatMPIAIJSetPreallocation(mat, 18, nullptr, 18, nullptr); CHKERRXX(ierr);

	    PetscPrintf(PETSC_COMM_WORLD, "Converting matrix to PETSc format...\n");

	    // parallelize matrix insertion (Sonnet 4.6)
		PetscInt row_start, row_end;
		MatGetOwnershipRange(mat, &row_start, &row_end);

		for (unsigned int i = 0; i < matrix->length; i++) {
			PetscInt x = matrix->entries[i].i;
			if (x >= row_start && x < row_end) {  // only insert locally owned rows
				PetscInt y = matrix->entries[i].j;
				PetscScalar value = wgms3d::maybeConvertComplexToReal(
					matrix->entries[i].v, PetscScalar());
				ierr = MatSetValues(mat, 1, &x, 1, &y, &value, INSERT_VALUES);
				CHKERRXX(ierr);
			}
		}
	    matrix.reset();

	    ierr = MatAssemblyBegin(mat, MAT_FINAL_ASSEMBLY); CHKERRXX(ierr);
	    ierr = MatAssemblyEnd(mat, MAT_FINAL_ASSEMBLY); CHKERRXX(ierr);

	    ierr = EPSCreate(PETSC_COMM_WORLD, &eps); CHKERRXX(ierr);
	    ierr = EPSSetOperators(eps, mat, NULL); CHKERRXX(ierr);
	    ierr = EPSSetProblemType(eps, EPS_NHEP); CHKERRXX(ierr);
	    ierr = EPSSetDimensions(eps, num_eigenvalues, PETSC_DECIDE, PETSC_DECIDE); CHKERRXX(ierr);
	    ierr = EPSSetTarget(eps, sigma); CHKERRXX(ierr);
	    ierr = EPSSetWhichEigenpairs(eps, EPS_TARGET_MAGNITUDE); CHKERRXX(ierr);
//	    ierr = EPSSetType(eps, EPSARPACK); CHKERRXX(ierr);

	    ST st;
	    ierr = EPSGetST(eps, &st); CHKERRXX(ierr);
	    ierr = STSetType(st, STSINVERT); CHKERRXX(ierr);

	    KSP ksp;
	    ierr = STGetKSP(st, &ksp); CHKERRXX(ierr);
	    ierr = KSPSetType(ksp, KSPPREONLY); CHKERRXX(ierr); // because we're using a direct solver (PCLU)

	    PC pc;
	    ierr = KSPGetPC(ksp, &pc); CHKERRXX(ierr);
	    ierr = PCSetType(pc, PCLU); CHKERRXX(ierr);
#ifdef WGMS3D_WITH_CUDA
		// Define the sparse direct solver to use for the LU factorization.
	    if(use_cuda) {
			ierr = PCFactorSetMatSolverType(pc, MATSOLVERCUSPARSE); CHKERRXX(ierr);
		}
		else {
			ierr = PCFactorSetMatSolverType(pc, MATSOLVERMUMPS); CHKERRXX(ierr);
		}
#else
		ierr = PCFactorSetMatSolverType(pc, MATSOLVERMUMPS); CHKERRXX(ierr);
//	    ierr = PCFactorSetMatSolverType(pc, MATSOLVERSUPERLU_DIST); CHKERRXX(ierr);
//	    ierr = PCFactorSetMatSolverType(pc, MATSOLVERSUPERLU); CHKERRXX(ierr);
#endif

	    // note: the default tolerance is 1e-8 instead of 1e-16. this has
	    // led to incorrect mode fields for the degenerate fundamental
	    // mode of a circular fiber: ./wgms3d -g ../fiber.mgp -l 1.55 -U
	    // -0.8:100:+0.8 -V -0.8:100:+0.8 -n 4, where fiber.mgp is from
	    // the tutorial.
	    ierr = EPSSetTolerances(eps, 1e-16, PETSC_DECIDE); CHKERRXX(ierr);

	    // Allow all solver settings to be overridden from the command line
	    // (e.g. -eps_ncv, -log_view, ...).
	    ierr = EPSSetFromOptions(eps); CHKERRXX(ierr);

		// Print out the solver in use, which is useful for debugging and performance comparisons.
		MatSolverType solver_in_use;
		PetscErrorCode qerr = PCFactorGetMatSolverType(pc, &solver_in_use);
		if(qerr == 0 && solver_in_use) {
			PetscPrintf(PETSC_COMM_WORLD, "Solver used for factorization: %s.\n", solver_in_use);
		}
		else {
			PetscPrintf(PETSC_COMM_WORLD, "Couldn't determine solver in use.\n");
		}
		// Verify that the active tolerance setting is not too high, which can lead to incorrect mode fields for degenerate modes.
		PetscReal active_tol;
		ierr = EPSGetTolerances(eps, &active_tol, NULL); CHKERRXX(ierr);
	    PetscPrintf(PETSC_COMM_WORLD, "Requiring tolerance=%.2e...\n", active_tol);

	    PetscPrintf(PETSC_COMM_WORLD, "Eigensolving using SLEPc (nev=%d)...\n", num_eigenvalues);
	    ierr = EPSSolve(eps); CHKERRXX(ierr);

	    int niter, nconv, ncv_actual, mpd_actual;
	    ierr = EPSGetIterationNumber(eps, &niter); CHKERRXX(ierr);
	    ierr = EPSGetConverged(eps, &nconv); CHKERRXX(ierr);
	    ierr = EPSGetDimensions(eps, NULL, &ncv_actual, &mpd_actual); CHKERRXX(ierr);
	    PetscPrintf(PETSC_COMM_WORLD,
			"Eigencalculation finished successfully (niter=%d, nconv=%d, ncv=%d, mpd=%d)\n",
			niter, nconv, ncv_actual, mpd_actual);
	    if(nconv < num_eigenvalues) {
		BOOST_THROW_EXCEPTION(std::runtime_error("Number of converged eigenpairs lower than requested. Terminating."));
	    }
	    if(nconv > num_eigenvalues) {
		PetscPrintf(PETSC_COMM_WORLD,
			    "Number of converged eigenpairs (%d) larger than requested (%d), ignoring.\n",
			    nconv, num_eigenvalues);
	    }

	    PetscInt maxit;
	    EPSType type;
	    PetscReal tol;
	    ierr = EPSGetType(eps,&type); CHKERRXX(ierr);
	    ierr = EPSGetTolerances(eps,&tol,&maxit); CHKERRXX(ierr);
	    PetscPrintf(PETSC_COMM_WORLD,"Used solution method=%s, tol=%.4g, maxit=%d.\n", type, tol, maxit);

	}

	~SlepcSolverResult ()
	{
	    freePetscMembers();
	}

	size_t getNumEigenpairs () const final
        {
	    int nconv = 0;
	    PetscErrorCode ierr = EPSGetConverged(eps, &nconv); CHKERRXX(ierr);
	    return size_t(nconv);
	}

	std::complex<double> getEigenvalue (size_t i) const final
	{
	    PetscScalar kr, ki;
	    PetscErrorCode ierr = EPSGetEigenvalue(eps, i, &kr, &ki); CHKERRXX(ierr);
	    return maybeMergeRealImaginary(kr, ki);
	}

	std::vector<std::complex<double>> getEigenvector (size_t i) final
	{
	    PetscErrorCode ierr;
	    std::vector<std::complex<double>> result;

	    if(!xr)
	    {
		ierr = MatCreateVecs(mat, &xr, nullptr); CHKERRXX(ierr);
		ierr = MatCreateVecs(mat, &xi, nullptr); CHKERRXX(ierr);
		ierr = VecCreateSeq(PETSC_COMM_SELF, rank == 0 ? n : 0, &local_vector); CHKERRXX(ierr);
	    }

	    PetscScalar kr, ki;
	    ierr = EPSGetEigenpair(eps, i, &kr, &ki, xr, xi); CHKERRXX(ierr);

	    scatterToLocalVector(xr);
	    if(rank == 0)
	    {
		PetscScalar *pLocalData;
		// note: must have this inside the loop:
		ierr = VecGetArray(local_vector, &pLocalData); CHKERRXX(ierr);
		result = std::vector<std::complex<double>>(pLocalData, pLocalData+n);
		ierr = VecRestoreArray(local_vector, &pLocalData); CHKERRXX(ierr);
	    }

	    if(ki != 0.0) {
		copyImaginaryPart<PetscScalar>(result);
	    }

	    return result;
	}

    };

} // anonymous namespace

std::unique_ptr<ISolverResult> eigenSolver (
    std::unique_ptr< sparse_matrix<std::complex<double>> > matrix,
    bool is_matrix_real,
    double sigma,
    int num_eigenvalues,
    bool use_cuda
    )
{
    if(!is_matrix_real && std::is_same<PetscScalar, double>::value)
    {
	BOOST_THROW_EXCEPTION(std::runtime_error(
	   "System matrix is complex. This version of wgms3d was compiled using "
	   "the real-scalar version of PETSc, but the complex-scalar version is "
	   "needed for this."));
    }
    
    return make_unique<SlepcSolverResult>(std::move(matrix), is_matrix_real, sigma, num_eigenvalues, use_cuda);
}
