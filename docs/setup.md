# Set up a research campaign

## Choose what to measure

Commit the starting source in your repository.
Drill evaluates committed files.
A worker must have a clean checkout before evaluation.

Create a configuration beside your evaluator adapter.
The [toy configuration](../examples/toy/hub.json) shows the complete format.
Use your own measurement code and data for a real project.
Set the objective, its unit, whether higher or lower is better, and any hard constraints.

An evaluator receives a request file and writes a result file.
The [adapter reference](adapters.md) defines both formats.
The agent already working in the repository is the default driver.
A separate coding-agent command is optional.

## Measure the baseline

Run these commands inside the target repository.

```sh
drill init --config research.json
drill baseline
```

Drill creates and selects a campaign named `default` on first use.
Initialization saves the source revision, tool code, configuration, adapters, and declared evaluator assets.
The baseline command performs the first evaluation.
A passing baseline is required before candidates can enter the comparison.

To create another campaign, give it a name.

```sh
drill init --config research.json --campaign another-search
```

If an evaluation returns PENDING, poll its saved attempt.

```sh
drill resume --attempt 000001
```

A failed baseline has no reference score.
If you change the saved evaluator or evaluation rules, create a new campaign.

## Make a candidate yourself

```sh
drill workspace
```

The output identifies the checkout, branch, and agent instructions for a worker named `researcher`.
Read the instructions, edit in that checkout, and commit the change.
Then evaluate from the worker checkout.

```sh
drill step --hypothesis "Explain why the change should improve the result"
```

Drill recognizes the worker's repository and campaign.
It snapshots the committed source before invoking the evaluator.
The evaluator writes generated files in the supplied output directory.
Changing the source snapshot invalidates the attempt.

Use a named worker for parallel research.

```sh
drill workspace --worker worker-a
```

Each worker has a separate branch and directory inside the repository.
Drill does not reset or remove an occupied worker.

## Run research with your assistant

Without a separate coding-agent command, Drill returns the worker, research context, instructions, and iteration budget to the current agent.
The current agent performs and evaluates each experiment using its existing login, model, and tools.
This workflow does not require a model endpoint or key in Drill.
Each repository can use a different assistant environment.
Drill does not start another model or choose an API.
An explicitly configured coding-agent command enables the subprocess loop.
Provider-specific invocation belongs in that adapter.
Installing Drill does not install or authenticate a separate coding agent.
The adapter receives the current best result and experiment history.
It must commit a new candidate and return its hypothesis.

```sh
drill run --iterations 5
```

Drill evaluates each candidate before requesting another.
It stops on a failed, invalid, pending, incomparable, or inconclusive result.
It preserves the checkout and logs if the agent fails or leaves changes uncommitted.
A rejected candidate remains in its worker checkout.
The agent can use the history to choose what to try next.

## Read and select campaigns

```sh
drill status
drill dashboard
drill use another-search
```

Open the dashboard path returned by the command.
The report works offline and links each attempt to its saved receipt.
Regenerate it after new experiments.

Commands use the selected campaign when you work in the repository root.
Commands inside a managed worker use that worker's campaign.
Explicit options take precedence.
Use them in scripts that run several campaigns.

```sh
drill status --repo /path/to/project --campaign another-search
```

Selecting a campaign changes only the repository's active selection file.
It does not upgrade an existing campaign's saved code or configuration.
Each campaign also has a launcher at `.drill/campaigns/<name>/hub.py` that operates only that campaign.
When calling the launcher directly, pass a worker or revision for a candidate evaluation.

## Keep results comparable

The evaluator must identify the actual data, runner, settings, and hardware in its result context.
A changed context prevents comparison.
Declare trusted evaluator scripts and small fixed inputs as evaluator assets so Drill saves their exact committed bytes.
Dependencies and external data remain the adapter's responsibility.

## Save goals and custom setup

Run `drill serve` in the project and open its localhost address.
Goals and setup belong to that repository and survive browser reloads and server restarts.
They do not rewrite a campaign's saved runtime, evaluation rules, or evidence.

The current repository agent remains the default.
An optional model connection requires an explicit endpoint, model, and environment-variable name for its API key.
The connection accepts a chat request with a model and user message and expects a text response in the first choice's message.
Remote endpoints require HTTPS; HTTP is supported for local model services.
Saving setup does not call the model.
Use the model form or `drill model --prompt "Your prompt"` to make an explicit request.
Model responses do not edit code or commit changes.

Source setup controls [submodule and Git LFS materialization](data.md) for newly initialized campaigns.
Existing campaigns keep their saved behavior.
Missing inputs cause an incomplete evaluation without a score.
Downloads remain disabled unless you enable them explicitly.
