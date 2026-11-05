# Restricted OpenCode research

This optional adapter lets OpenCode edit a research candidate while Drill owns committing and evaluation.
It uses ordinary OpenCode by default and inherits the user's configured model.
Drill's core does not require OpenCode, ASU, or XOR.

## Install and prepare

Install Drill and configure an OpenCode 2 provider before using the adapter.
OpenCode 2.2.5 is the version checked during development.
Other versions must expose the same effective-agent inspection and permission contract or the adapter refuses to start.

Copy [the example configuration](config.json) and [adapter script](agent.py) together into your repository.
Keep the script beside the copied configuration, and replace the evaluator path, objective, constraints, research brief, and editable files for your project.
The supplied evaluator is only the deterministic parameter example.
Its measurements are not model qualification.

Initialize a fresh campaign and measure its baseline before running experiments.
Use an absolute configuration path when the configuration lives outside your repository.

```sh
drill init --config /path/to/research.json
drill baseline
drill run --iterations 3
```

The configuration supplies the experiment limit and evaluation time budget.
The agent timeout must leave time for assistant startup, editing, and the host commit.
No assistant model is silently selected by this adapter.
To supply a different launcher, use this coding-agent section in the copied configuration and replace the final argument with your executable name or path.

```json
{
  "agent": {
    "adapter": "agent.py",
    "timeout_seconds": 240,
    "command": ["{python}", "{adapter}", "{request}", "{result}", "--launcher", "opencode"]
  }
}
```

## Choose a launcher

The command adapter accepts an optional launcher argument.
Set its command to Python, the saved adapter file, the request file, the result file, and then the launcher option.
The normal command substitutions are documented in [the adapter reference](../../docs/adapters.md).
For example, append `--launcher opencode-asu` to choose your existing ASU wrapper.
A different wrapper or executable path works through the same option.
The adapter never changes global provider settings.
An explicit model option is available when the user wants to override the launcher's default.

## Restricted actions

The model can read tracked regular files from the supplied baseline checkout and edit only the exact listed files.
Ignored and untracked files are not granted read permission.
Shell commands, network tools, delegation, skills, and other tool actions are denied by default.
No blanket auto-approval flag is used.
Permitted reads and edits run without approval prompts.
A refused or failed tool call stops the candidate from being committed or evaluated.

Before launching the model, the adapter inspects the effective research agent and its working directory.
It refuses a launcher that ignores the requested permission rules or selects another directory.
Project configuration is disabled for this invocation; the user's trusted global provider profile remains available.
A retained per-run configuration file supplies the restricted policy.
Inherited custom configuration-file or inline overrides cause a refusal because replacing them could change model routing.
Configure the provider through the global profile or a profile directory before using this adapter.
Global files are not edited.
The model receives the research brief, objective, constraints, current best result, editable files, evaluation budget, and summaries of the ten most recent attempts.
Hypotheses and reasons are limited to 256 characters per summary, with the full journal retained by Drill.
The total attempt count makes the bounded history explicit.
Open exact files directly; directory reads remain denied.
Drill supplies the baseline checkout.

The host checks the worker branch, unchanged starting commit, exact changed files, and clean result.
Only then does it create a normal commit, with repository commit hooks and signing disabled for that host operation.
No reset or cleanup removes failed edits.
The candidate, permission proof, event stream, and errors remain available for inspection.

## Limits

This is a tool permission policy, not operating-system containment.
A configured launcher, global plugin, Git configuration, or evaluator is trusted executable code.
Those programs can perform actions outside model tool permissions.
Do not use this adapter as a sandbox for untrusted programs.

This adapter currently edits existing regular files.
Creating or deleting files is supported by the campaign's broader candidate contract but is not enabled by this adapter.
Editable filenames cannot contain permission-pattern characters or control characters.
The permission inventory lives in the per-run file rather than a large environment string.
The research prompt is limited to 64 KiB and includes at most 64 example baseline filenames, so large repositories do not expand every tracked filename into model context.
Use a focused editable scope and research brief.

## Verify your launcher

The live check makes one model request to edit a generated fixture and another to attempt a forbidden edit.
It uses the launcher's configured provider and may consume model usage.
It requires no real project files or private data.

```sh
python3 examples/opencode/check_live.py --output .checks/opencode-live.json
python3 examples/opencode/check_live.py --launcher opencode-asu --output .checks/opencode-asu-live.json
```

A passing result requires a permitted edit, a clean host-created commit, a real runtime refusal of the forbidden edit, and unchanged protected input.
The check does not establish model quality, operating-system containment, or compatibility with every OpenCode version.
