#!/usr/bin/env python3

import argparse
import math
import re
import subprocess
import sys


def split_joined_args(value: str) -> list[str]:
    if not value:
        return []
    return [item for item in value.split("|") if item]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--test-name", required=True)
    parser.add_argument("--wgms3d-bin", required=True)
    parser.add_argument("--working-directory", required=True)
    parser.add_argument("--case-args", required=True)
    parser.add_argument("--grid-args", required=True)
    parser.add_argument("--expected-neff", required=True)
    parser.add_argument("--rel-tol", required=True, type=float)
    args = parser.parse_args()

    command = [
        args.wgms3d_bin,
        *split_joined_args(args.case_args),
        *split_joined_args(args.grid_args),
    ]
    expected = [float(value) for value in split_joined_args(args.expected_neff)]

    result = subprocess.run(
        command,
        cwd=args.working_directory,
        capture_output=True,
        text=True,
        check=False,
    )

    output = result.stdout + result.stderr
    if result.returncode != 0:
        sys.stderr.write(
            f"{args.test_name}: wgms3d failed with exit code {result.returncode}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}\n"
        )
        return 1

    matches = re.findall(r"EV\s+\d+:\s+n_eff = ([^\s]+)", output)
    if len(matches) < len(expected):
      sys.stderr.write(
          f"{args.test_name}: expected at least {len(expected)} eigenvalue lines, got {len(matches)}\n"
          f"output:\n{output}\n"
      )
      return 1

    for index, expected_value in enumerate(expected, start=1):
        computed_value = float(matches[index - 1])
        abs_error = abs(computed_value - expected_value)
        rel_error = abs_error / abs(expected_value)
        print(
            f"{args.test_name}: mode {index} expected={expected_value:.15f} "
            f"computed={computed_value:.15f} rel_error={rel_error:.6e}"
        )
        if not math.isfinite(computed_value):
            sys.stderr.write(
                f"{args.test_name}: mode {index} produced a non-finite n_eff value\n"
            )
            return 1
        if rel_error > args.rel_tol:
            sys.stderr.write(
                f"{args.test_name}: mode {index} exceeded tolerance\n"
                f"expected={expected_value:.15f}\n"
                f"computed={computed_value:.15f}\n"
                f"abs_error={abs_error:.6e}\n"
                f"rel_error={rel_error:.6e}\n"
                f"tolerance={args.rel_tol:.6e}\n"
            )
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())