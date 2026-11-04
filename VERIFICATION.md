# Verify Drill

Run the command checks and complete toy research loop from the repository root.

```sh
python3 tools/verify.py --output .checks/verification.json
```

The verifier exercises actual temporary Git repositories, candidate comparisons, source snapshots, worktree ownership, resumable jobs, evidence checks, campaign selection, and the command entry point.
It also checks Python syntax and the project's source-comment rule.
The toy task uses exact arithmetic rather than model inference or a performance benchmark.

To check the XOR adapter against an existing XOR checkout, add its repository path.

```sh
python3 tools/verify.py --output .checks/verification.json --xor-repo /path/to/xor
```

These adapter checks use synthetic evidence.
They do not train, measure, or qualify a model.

The [blast-radius review](docs/blast-radius.md) links the executable safety proof and open concerns.
The repository's CI repeats the core checks and installed-package workflow on supported Python versions.

To check a built wheel, run `python3 tools/check_package.py /path/to/drill.whl`.
The package check installs into a temporary directory, runs five experiments with the default commands, and checks the license files and saved launcher.
