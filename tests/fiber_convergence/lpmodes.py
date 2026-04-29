#!/usr/bin/env python3
"""
Convergence study: Keep CD constant, vary grid size.
Python version of lpmodes.m
"""

import numpy as np
import subprocess
import matplotlib.pyplot as plt
import re
from pathlib import Path

# Reference effective indices for 6 modes
neffreal = np.array([2.370506655212511e+00,
                     2.161722239629984e+00,
                     2.161722239629984e+00,
                     1.865029549757501e+00,
                     1.865029549757501e+00,
                     1.770543445693141e+00])

# Line styles for plotting
ls = ['x-', 'xr-', 'xr-', 'x--', 'x--', 'xk-']

# Grid sizes to test
Ns = np.linspace(50, 400, 25)
# Ns = np.linspace(50, 100, 11)
Ns = np.floor(Ns).astype(int)

# Initialize array to store neff values
neffs = np.full((len(neffreal), len(Ns)), np.nan)

# Base command template
wgms3d_cmd = './build/wgms3d -d -l 10 -p -g tests/fiber_convergence/fiber.mgp'  # -s sets the search n_eff for the first mode

# Get current directory
cwd = Path.cwd()

def parse_neff_from_output(output_text):
    """
    Extract neff values from wgms3d output.
    Looks for lines with 'n_eff = ' followed by a complex number.
    
    Args:
        output_text: String containing wgms3d output
        
    Returns:
        List of neff values (real part only) found in output
    """
    neff_values = []
    
    # Pattern: Match eigenvalue lines "EV   0: n_eff = 2.370... + i ..."
    # The "EV" prefix ensures we skip the "Searching for modes near n_eff = 2.5" line
    pattern = r'^EV\s+\d+:\s+n_eff\s*=\s*([-+]?\d+\.\d+(?:[eE][-+]?\d+)?)'
    matches = re.findall(pattern, output_text, re.MULTILINE)
    
    if matches:
        neff_values = [float(m) for m in matches]
    
    return neff_values

# Run convergence study
print(f"Starting convergence study with {len(Ns)} grid sizes...")
print(f"Grid sizes: {Ns}")

for Nc, N in enumerate(Ns):
    # Construct command for this grid size
    cmd = f"{wgms3d_cmd} -U -9.99:{N}:9.99 -V -9.99:{N}:9.99 -n 6"
    
    print(f"\nProgress: {Nc+1}/{len(Ns)}")
    print(f"Running with grid size N={N}...")
    
    try:
        # Run the command
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=300)
        
        # Parse output to extract neff values
        output = result.stdout + result.stderr
        modes_neff = parse_neff_from_output(output)
        
        if modes_neff:
            # Store the neff values (up to 6 modes)
            for i in range(min(len(modes_neff), len(neffreal))):
                neffs[i, Nc] = modes_neff[i]
            print(f"  Found {len(modes_neff)} modes")
            print(f"  neff values: {modes_neff[:6]}")
        else:
            print(f"  Warning: Could not parse neff values from output")
            print(f"  Return code: {result.returncode}")
            if result.stderr:
                print(f"  stderr: {result.stderr[:200]}")
                
    except subprocess.TimeoutExpired:
        print(f"  Warning: Command timed out for N={N}")
    except Exception as e:
        print(f"  Error running command: {e}")

# Create convergence plot
plt.figure(figsize=(10, 8))

for i in range(len(neffreal)):
    # Calculate relative errors
    relerrs = np.abs(neffs[i, :] - neffreal[i]) / neffreal[i]
    
    # Plot on log-log scale (x-axis: 1/N)
    valid_mask = ~np.isnan(relerrs)
    if np.any(valid_mask):
        plt.loglog(1.0 / Ns[valid_mask], relerrs[valid_mask], ls[i], label=f'Mode {i+1}')

plt.xlabel('Resolution (inverse grid-point distance) [a.u.]')
plt.ylabel('Relative error in $n_{eff}$')
plt.title(f'Convergence Study: {cwd.name}/lpmodes.py')
plt.ylim([1e-8, 1])
plt.grid(True, which='both', alpha=0.3)
plt.legend(loc='best')
plt.tight_layout()

# Show figure interactively (no file output)
plt.show()

print("\nConvergence study complete!")
print(f"neffs shape: {neffs.shape}")
print(f"neffs:\n{neffs}")
