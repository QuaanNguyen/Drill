# Adapter protocol

## Configuration

Configuration schema version 1 retains the original workflow.
Version 2 enables the optional research contract and prevents older clients from ignoring its restrictions.
Version 3 additionally enables exact evaluation-source selection.
The evaluator and agent request/result wire schema remains version 1.
The objective contains a metric name, maximize or minimize direction, display unit, and nonnegative minimum absolute improvement.
Strict improvement is always required.
Zero and negative objective values are supported.
Constraints compare named metrics with finite numeric thresholds using <=, >=, or ==.
Boolean values are not numeric measurements.

Each evaluator or agent adapter declares a file, a positive timeout, and an optional command argument list.
The default argument list launches the file with the current Python interpreter and passes request and result filenames.
Commands run without a shell.
The supported substitutions are `{python}`, `{adapter}`, `{request}`, and `{result}`.
For a JavaScript adapter, set the command to the following list.

```json
["node", "{adapter}", "{request}", "{result}"]
```

Adapter file paths resolve relative to the configuration file during initialization.
The hub copies each adapter into the frozen campaign.
An evaluator can declare assets as a list of repository-relative paths.
Each asset must be a tracked regular file in the campaign's starting commit.
The hub copies those exact bytes into the frozen assets directory.
An adapter is a single executable file plus declared assets.
Imports of undeclared local helper files are not bundled automatically.

## Evaluation requests

The evaluator's working directory is a separate snapshot of the selected commit.
The request JSON has this shape.

```json
{
  "schema_version": 1,
  "attempt_id": "000002",
  "role": "candidate",
  "operation": "start",
  "source": {
    "path": "/absolute/campaign/attempts/000002/source",
    "commit": "full-git-commit",
    "tree": "git-tree"
  },
  "evaluation_fingerprint": "sha256-of-frozen-campaign-inputs",
  "objective": {"metric": "accuracy", "direction": "maximize", "unit": "fraction", "min_improvement": 0.01},
  "constraints": [{"metric": "unsafe_approvals", "op": "==", "value": 0}],
  "assets": "/absolute/campaign/evaluation/assets",
  "output_dir": "/absolute/campaign/attempts/000002/artifacts",
  "reference": {"attempt_id": "000001", "source_commit": "full-reference-commit", "metrics": {"accuracy": 0.8}}
}
```

The actual reference contains the full saved best accepted receipt.
A baseline request has a null reference and a baseline role.
An adapter must evaluate the supplied source snapshot rather than the live repository checkout.

## Evaluation responses

Write one JSON object to the supplied result filename.
Echo all identity fields from the request.
A successful response has this shape.

```json
{
  "schema_version": 1,
  "attempt_id": "000002",
  "source_commit": "full-git-commit",
  "evaluation_fingerprint": "sha256-of-frozen-campaign-inputs",
  "status": "complete",
  "context": {"dataset_sha256": "actual-data-hash", "runner_sha256": "actual-runner-hash", "machine": "actual-machine-id"},
  "metrics": {"accuracy": 0.86, "unsafe_approvals": 0},
  "interval": [0.85, 0.87],
  "artifacts": ["measurements.json", "evaluation.log"]
}
```

The context must be a nonempty JSON object describing the actual comparison setup.
The optional interval is a lower and upper bound containing the objective value.
Without an interval, the comparison treats the objective as an exact reported point.
When intervals are present, they must establish the configured improvement without overlap.
The hub does not infer statistical confidence from repeated measurements.

Every complete response must list at least one regular artifact file under the supplied output directory.
Artifact paths are relative and cannot escape that directory.
The hub computes and retains their hashes.
Artifacts, requests, responses, logs, source inventories, and final receipts are rechecked when read.
A missing metric or malformed response is INVALID.
A failed constraint is REJECTED.
Different contexts are INCOMPARABLE.
An uncertain improvement is INCONCLUSIVE.
A passing baseline is BASELINE, and a passing improved candidate is ACCEPTED.

A failed or inconclusive response uses `failed` or `inconclusive` as its status and includes a nonempty reason.
Metrics are not required for those statuses and cannot supply a score.
A nonzero process exit is FAILED even if a result file claims success.
A timeout terminates the process group and records INCONCLUSIVE with retained logs.

## Pending jobs

An external evaluator can submit a remote job and return a pending result with the same identity fields.
It must include a job object with a stable, nonempty identifier.

```json
{"status": "pending", "job": {"id": "service-job-123", "other_polling_data": "adapter-owned"}}
```

The fragment above omits identity fields for brevity.
Resume invokes the same frozen adapter with `poll` as its operation and the saved job object.
The job identifier cannot change during polling.
The adapter owns all remote service details, credentials, and request idempotency.
The hub never retries a start request automatically.
A running attempt left by a crash remains incomplete and cannot become an incumbent.
Inspect the saved request and service evidence before explicitly starting another attempt.

## Research requests

A campaign with a [research section](research.md) includes its normalized brief, editable file list, iteration limit, and local evaluator time budget in evaluation and agent requests.
Coding-agent requests also identify the initial campaign commit and the prepared starting revision.
Adapters must not interpret the supplied brief as permission to change the evaluator, frozen assets, or tool policy.
The campaign validates candidate scope before invoking an evaluator.

## Coding-agent requests

The optional agent adapter runs inside its managed Git worktree.
Its request contains the worker's path and branch, the current best accepted result, objective, constraints, full experiment history, and the campaign instructions path.
It must commit a new clean source revision and write the following response.

```json
{"hypothesis": "Explain why this committed change should improve the configured objective."}
```

The hub rejects a dirty checkout or an unchanged commit.
It does not execute generated shell instructions itself.
The configured adapter owns invocation of a real coding agent and is trusted to respect campaign ownership.
Agent output, request, response, and evaluation linkage are retained under the campaign's agent-runs directory.

## Trust and supported repositories

Adapters execute with the user's permissions.
They can access external data and services, so the hub cannot prove undeclared dependencies or self-reported measurements.
Pin evaluators and identify all meaningful comparison inputs in the response context.
Acceptance is limited to the configured checks and does not itself establish publication, release, or model qualification.

The first version supports macOS and Linux with POSIX locks and process groups.
Committed source snapshots support ordinary files, directories, and symlinks that remain inside the snapshot.
Escaping symlinks are rejected.
Git submodules require explicit [materialization](data.md).
Git LFS files require explicit materialization and verified object bytes before evaluation.
Untracked files, local dependency directories, and ignored files are not included in source snapshots.

## Select only the source an evaluator needs

Configuration version 3 can declare exact source files for each snapshot.
Older clients refuse this version rather than silently including the whole repository.

```json
{
  "schema_version": 3,
  "evaluator": {
    "source_paths": ["src/audit.py", "src/helpers.py"]
  }
}
```

Merge this fragment into a complete configuration with its adapter, objective, and other required settings.
Every selected path must be a tracked regular file at the evaluated revision.
Names are literal; directories and wildcard expansion are not supported.
A missing selected file makes the attempt invalid without a score.
Without this field, snapshots retain the existing whole-repository behavior.

This allows a small source experiment inside a repository containing unrelated model artifacts or submodules.
Only selected dependencies are materialized, using the same explicit download and byte-verification rules.
A selected LFS pointer still requires LFS materialization; selection does not treat pointers as model bytes.
Evaluator assets are captured separately and only for their declared paths.
Research scope checks still inspect the whole candidate commit, including files excluded from the evaluator snapshot.
The saved configuration, snapshot inventory, commit identity, and request retain the selection.
