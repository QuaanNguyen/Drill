# How Drill runs an experiment

A campaign owns its configuration, saved tool code, evaluator, and experiment evidence.
A worker owns one Git branch and one checkout inside the target repository.
An evaluator measures a committed source snapshot and returns structured results.
The comparison code decides whether those results improve the current best accepted experiment.

## Installation and repository ownership

Drill is installed once per machine or environment as a Python command-line tool.
The installed command discovers the target Git repository from the current directory.
Each repository owns its campaigns, evaluator adapters, settings, and worker checkouts.
Campaign initialization saves the runtime needed to preserve that campaign's behavior independently of installed tool upgrades.
A saved runtime is not a clone of the Drill development repository.

The current-agent handoff is the default research driver.
The assistant keeps its own authentication, model selection, and tools.
An optional coding-agent adapter owns launching a separate assistant.
Direct model connections are optional text requests and do not drive the research loop.

A future cross-repository dashboard is tracked in [the repository overview ticket](https://github.com/QuaanNguyen/Drill/issues/12).
It should reference repository-owned campaigns and preserve their execution and evidence ownership.

## Code ownership

`cli.py` resolves the repository and selected campaign and invokes its saved launcher.
`engine.py` creates campaigns, executes adapters, polls saved jobs, and runs bounded agent loops.
`workspace.py` creates committed source snapshots and owns worker paths and Git registration checks.
`model.py` validates adapter results and compares objectives and constraints.
`store.py` writes receipts, checks saved evidence, and derives the current best result.
`report.py` builds the offline dashboard from checked receipts.

## Campaign selection and saved code

The repository stores its active selection outside every campaign.
Changing that selection cannot alter a campaign's saved runtime or evaluator.
Existing commands dispatch through the campaign's own launcher.
A campaign must be recreated to use changed evaluation rules or tool code.

## Evidence and comparison

Each attempt records an exact Git commit and snapshots its files before evaluation.
Requests, responses, logs, source inventories, and artifact hashes stay with the attempt.
Drill checks that the evaluator did not change the source snapshot.
The reader checks saved receipts and source inventories again before using a result.
If an accepted reference becomes invalid, results that depend on it also become invalid.

A candidate must improve the latest accepted result, including when an older pending job finishes late.
Comparison supports higher-is-better and lower-is-better objectives, absolute improvement thresholds, and numeric constraints.
Optional uncertainty intervals must establish the required improvement without overlap.
The evaluator's context must match the reference context.

## Limits

Adapters run with the user's permissions.
They are trusted code and must report actual measurements and comparison inputs.
The core cannot prove whether an external dataset, timing, or human review claim is true.
An accepted result does not publish a release or establish model qualification.

The first version uses POSIX locks and process groups on macOS and Linux.
Source snapshots include committed regular files and contained symlinks.
They reject symlinks that escape the snapshot.
Submodules and LFS objects require explicit materialization options and exact identity checks.
Submodule and LFS downloads are disabled by default and use owned temporary stores when explicitly enabled.
Other dependencies and remote evaluation services need project-specific adapters.

## Local dashboard

The loopback server reads each campaign through its saved launcher.
Goals and nonsecret setup live outside campaign evidence.
The server reads API keys from environment variables only for explicit model requests.
Cross-origin changes and model redirects are rejected.
The UI uses system color preferences and matching monochrome SVGs.

## Portable research campaigns

The optional research contract belongs to the campaign, independently of assistant launchers and evaluator implementations.
The research module validates exact file scope against the initial revision and prepares incumbent-based checkpoint commits in owned workers.
It retains losing commits rather than resetting branches.
The command routes research handoffs through their saved launcher, so an installed client does not replace a campaign's research semantics.
Assistant-specific tool restrictions belong in optional adapters.
The core does not depend on XOR or any provider profile.
See [research behavior and trust limits](docs/research.md).
