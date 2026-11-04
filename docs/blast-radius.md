# Publication blast-radius review

## What changed

Drill now remembers the selected campaign and recognizes the repository and worker from the current checkout.
Existing repository, campaign, worker, and revision options still work.
The publication also adds Apache 2.0 licensing, a wide README banner, shorter setup instructions, and automated command and package checks.

## The safety fact

Selecting a campaign and using the shorter commands must preserve an existing campaign's saved runtime, configuration, evidence, and worker ownership.
New commands must still dispatch through that campaign's saved launcher.

This fact reached proof level 4 through executed checks against a real campaign created by the previous command implementation.
The new client selected the old campaign, read its results, and evaluated a candidate from its existing worker.
Every protected file retained its original hash, and the old launcher handled the evaluation.
An independent review also checked historical attempt files and Git references and found no changes to them.

The [captured result](proofs/campaign-compatibility.json) comes from the executable compatibility check.
Run it with a checkout of the previous version.

```sh
python3 tools/check_campaign_compatibility.py --previous /path/to/previous-checkout
```

The check rejects an identical command implementation so it cannot claim version compatibility by testing the same client twice.

Campaign selection lives outside the saved runtime.
See [selection](../drill/cli.py#L55) and [dispatch](../drill/cli.py#L113).
The selection and worker command tests also check that saved campaign files remain unchanged.

## Risks found and cleared

A normal Git worktree could resolve `HEAD` in the main checkout instead of its current checkout.
That could waste an evaluation and attach a hypothesis to the wrong source.
The fix resolves the current checkout's exact commit when both checkouts share the same Git repository.
The regression creates a real linked worktree with a different commit and requires the recorded commit and score to match it.
See [source resolution](../drill/cli.py#L29) and [the recorded finding](https://github.com/QuaanNguyen/Drill/issues/1).

Concurrent campaign selections could collide on a single temporary filename.
One command could fail after another command renamed that file.
The fix gives each JSON write its own temporary file before atomic replacement.
The regression synchronizes two real command processes at their file-flush boundary and requires both to succeed without leftover temporary files.
See [JSON writes](../drill/store.py#L27) and [the recorded finding](https://github.com/QuaanNguyen/Drill/issues/2).

Explicit options, managed-worker ownership, dirty-checkout rejection, changed-evidence detection, delayed-result comparison, and invalid-metric rejection passed their command-level checks.
The installed package includes the license files, runs the five-experiment toy loop, and produces a saved launcher that works independently of the installation.

The public export excludes local audit history, campaign state, worktrees, credentials, and machine-specific absolute paths.
The private extraction history remains local.

## Remaining concerns

- A real coding-agent adapter is still required for users who want the automatic loop to edit a real project.
  The supplied agent is a deterministic example, so this affects every user without their own adapter.
  The completion check is a real assistant run with a bounded iteration budget and preserved worker ownership.
  See [the coding-agent adapter task](https://github.com/QuaanNguyen/Drill/issues/3).
- The XOR adapter has synthetic-evidence coverage, but no real model measurement or qualification result from this publication.
  Treating those tests as a model result would be incorrect.
  Completion requires reviewed native evidence under XOR's existing checks.
  See [the native XOR evidence task](https://github.com/QuaanNguyen/Drill/issues/4).
- Dashboard content and evidence links pass checks, but its browser layout still needs a completed visual review.
  Layout defects remain unproven until desktop and narrow-width screenshots exist.
  See [the dashboard review task](https://github.com/QuaanNguyen/Drill/issues/5).
- Source snapshots reject Git submodules and retain Git LFS pointer text.
  This blocks automatic use of those dependencies and data unless an adapter materializes them.
  Completion requires explicit, hashed materialization with failure checks for unavailable or changed objects.
  See [the external-data task](https://github.com/QuaanNguyen/Drill/issues/6).

## Before merging command changes

Run the core verifier and any focused regression for the affected behavior.

```sh
python3 tools/verify.py --output .checks/verification.json
```

Build and check the installed package when changing commands or packaging.

```sh
python3 -m pip wheel --no-deps --wheel-dir .checks/dist .
python3 tools/check_package.py .checks/dist/*.whl
```

Use the previous-version compatibility check when changing campaign routing or saved runtime behavior.
Adapters remain trusted code, and their external measurements and data require project-specific checks.
