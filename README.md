<p align="center">
  <img src="assets/banner.svg" alt="Drill" width="100%">
</p>

Drill runs research experiments in a Git repository.
Provide an evaluator for your project.
The agent already working in your repository can drive the research while Drill compares committed changes against the best accepted result.
Each experiment keeps its hypothesis, source revision, measurements, and evidence.

## Install

Use Python 3.11.8 or later and Git on macOS or Linux.
Drill has no runtime package dependencies.

Install [pipx](https://pipx.pypa.io/stable/installation/), then install Drill once per machine or environment.
The installer exposes the `drill` command on your command search path and keeps its Python environment separate from your projects.

```sh
pipx install git+https://github.com/QuaanNguyen/Drill.git
drill --help
```

Run `drill` inside any target Git repository.
You do not need a Drill source checkout or a copy of Drill in every repository.
Your project can use any programming language.
Each repository keeps its own configuration, evaluator, campaigns, and evidence.
Existing campaigns retain their saved tool code when the installed tool is upgraded.

To upgrade the installed command, run:

```sh
pipx upgrade drill
```

For development, clone this repository and install your checkout with `python3 -m pip install -e .`.

## Try the example

This example requires a Drill development checkout.

```sh
python3 examples/toy/demo.py /tmp/drill-demo
```

The example creates a separate repository and runs five experiments with a deterministic agent.
It prints the dashboard path when the search finishes.
Choose a new destination each time.

## Use your repository

Prepare a [configuration and evaluator](docs/setup.md) for the result you want to improve.
By default, the agent already working in your repository drives the research.
Your assistant keeps its existing login and model selection; Drill does not require model credentials for this workflow.
Configure a separate coding-agent command only when you want Drill to launch one.
Then run these commands inside your repository.

```sh
drill init --config research.json
drill baseline
drill run --iterations 5
drill dashboard
```

Without a coding-agent adapter, the research command returns instructions and context for your current assistant.
The assistant makes and evaluates the experiments using its existing tools.

Drill remembers the selected campaign.
Use `drill status` to read its results or `drill use <name>` to switch campaigns.
You can still pass the repository and campaign explicitly when running several searches.

To make a change yourself, run `drill workspace`, edit and commit in the returned checkout, then run `drill step --hypothesis "Explain the expected improvement"` from that checkout.
Workers stay inside your repository under `.worktrees/drill/<campaign>/<worker>/`.
Drill keeps existing edits and refuses occupied paths or conflicting branches.

## Run bounded research

Define the research brief, the exact files the agent may change, and an experiment budget in a [research configuration](docs/research.md).
Drill rejects changes outside that scope and preserves rejected commits while preparing the next experiment from the best accepted result.
Use your current agent or an optional coding-agent adapter.
The workflow works through project evaluators without depending on a particular model provider, dataset, or hardware setup.

## Open the dashboard

```sh
drill serve
```

Open the localhost address printed by the command.
The dashboard follows your system's light or dark appearance and switches the logo with it.
Save goals in the sidebar and use Setup for new-campaign data options.
The optional model connection sends explicit text requests; it does not drive research or edit code.
API keys stay in the server's environment rather than saved settings.
The default research driver remains your current repository agent.

## Connect your tools

The [adapter reference](docs/adapters.md) describes evaluator and coding-agent commands.
The [XOR example](examples/xor/README.md) shows how to compare native model evidence while keeping XOR's qualification checks.
Its tests use synthetic evidence and do not establish a model improvement.

Drill compares results under the same reported evaluation setup.
Missing measurements and changed evidence cannot become the best result.
Acceptance means the configured checks passed.
Publication and model qualification remain separate project decisions.

## Development

Run `python3 tools/verify.py --output .checks/verification.json` to check the command workflow and example.
Read [the architecture](ARCHITECTURE.md) for how campaigns keep their runtime and evidence.
The [blast-radius review](docs/blast-radius.md) records the safety proof and links to open concerns.

## License

[Apache License 2.0](LICENSE).
