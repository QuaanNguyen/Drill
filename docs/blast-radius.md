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

## Dashboard and data follow-up

The default research driver is the agent already working in the repository.
A bounded handoff supplies the owned checkout, goal history, objective, constraints, and experiment history.
Separate coding-agent commands remain explicit configuration.
The local dashboard offers an optional chat-completions connection, called only after the user submits a prompt.
Tests exercise a real local HTTP service, environment-only credentials, rejected cross-origin writes, and sanitized failures.
No external model provider was called during verification.
See [the agent integration task](https://github.com/QuaanNguyen/Drill/issues/3).

The dashboard uses automatic light and dark media preferences with matching SVG assets.
Manual browser review covered both appearances, a narrow layout, saved goals and setup after reload, local model calls, empty campaigns, and all experiment decisions.
The browser review found small chart labels on narrow screens; the chart now uses the available width with readable labels.
See [the dashboard review task](https://github.com/QuaanNguyen/Drill/issues/5).

Submodules and Git LFS files can be materialized explicitly from local Git storage.
Fetching missing inputs requires a separate opt-in.
Submodules use exact recorded commits; LFS bytes must match their recorded hash and size.
Real Git fixtures cover nested submodules, local remotes, missing inputs, altered objects, and evaluator assets.
Existing campaigns retain their saved runtime and configuration.
See [data support](data.md) and [the external-data task](https://github.com/QuaanNguyen/Drill/issues/6).

The independent follow-up review found no remaining source blockers after fixes for credential-error disclosure and hidden integrity warnings.
The core verifier passed 52 tests and eight synthetic XOR adapter tests.
The previous-version compatibility check preserved all 17 protected files.

## Remaining concern

The XOR adapter has synthetic-evidence coverage, but no real model measurement or qualification result from this publication.
Treating those tests as a model result would be incorrect.
Completion requires reviewed native evidence under XOR's existing checks.
See [the native XOR evidence task](https://github.com/QuaanNguyen/Drill/issues/4).

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

## Portable research follow-up

New research campaigns require configuration version 2.
An older client refuses that version before creating a campaign, instead of silently ignoring scope restrictions.
Existing campaign runtime, configuration, and evidence retain their original hashes.

Candidate validation checks exact changed paths against the initial revision before invoking an evaluator.
Tests include renamed files, symlinks, Git pathspec syntax, and literal framework route filenames.
Progression uses checkpoint commits and fast-forward merges, retaining rejected commits and refusing dirty or colliding files.

The optional OpenCode adapter checks the effective directory and exact tool permissions before invoking the configured model.
Live checks with ordinary OpenCode and a caller-selected ASU launcher completed permitted edits and refused actual forbidden edits.
Both also completed a full Drill baseline, edit, host commit, and evaluation flow.
Cancellation checks cover an assistant that ignores termination and an exiting parent with a surviving descendant.
The adapter kills its owned child group before the campaign's outer termination deadline.

The [recorded proof](proofs/universal-research.json) and [decision trail](changes/universal-research-decisions.tsv) separate these guarantees from operating-system containment and model qualification.
Global plugins, configured launchers, Git configuration, and arbitrary adapters remain trusted code.
The optional OpenCode adapter currently edits existing regular files and refuses permission-pattern filenames or inherited custom configuration overrides.
The provider-neutral core supports a broader literal file scope through other adapters and the current-agent handoff.

## Real-repository input acquisition

An LFS-heavy repository exposed two acquisition paths outside the intended experiment.
Creating a worker could invoke Git LFS smudge, and freezing a few evaluator assets traversed unrelated model data.
A real Git LFS endpoint recorded two unexpected requests before the worker fix and zero afterward.
Exact evaluator source selection now excludes unrelated inputs, while selected LFS data still requires explicit verified materialization.
Asset capture also includes only the declared assets.

Configuration version 3 prevents older clients from silently ignoring the new selection.
Candidate scope validation still checks the whole commit, not only selected evaluator inputs.
The [proof](proofs/focused-source-inputs.json) records 84 core tests, explicit materialization regressions, installed-package checks, and unchanged hashes for 22 prior campaign files.
See the tracked [worker acquisition issue](https://github.com/QuaanNguyen/Drill/issues/9) and [focused input issue](https://github.com/QuaanNguyen/Drill/issues/10).
