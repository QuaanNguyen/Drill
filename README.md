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

```sh
git clone https://github.com/QuaanNguyen/Drill.git
cd Drill
python3 -m pip install .
drill --help
```

## Try the example

```sh
python3 examples/toy/demo.py /tmp/drill-demo
```

The example creates a separate repository and runs five experiments with a deterministic agent.
It prints the dashboard path when the search finishes.
Choose a new destination each time.

## Use your repository

Prepare a [configuration and evaluator](docs/setup.md) for the result you want to improve.
By default, the agent already working in your repository drives the research.
Configure a separate coding-agent command only when you want Drill to launch one.
Then run these commands inside your repository.

```sh
drill init --config research.json
drill baseline
drill run --iterations 5
drill dashboard
```

Drill remembers the selected campaign.
Use `drill status` to read its results or `drill use <name>` to switch campaigns.
You can still pass the repository and campaign explicitly when running several searches.

To make a change yourself, run `drill workspace`, edit and commit in the returned checkout, then run `drill step --hypothesis "Explain the expected improvement"` from that checkout.
Workers stay inside your repository under `.worktrees/drill/<campaign>/<worker>/`.
Drill keeps existing edits and refuses occupied paths or conflicting branches.

## Open the dashboard

```sh
drill serve
```

Open the localhost address printed by the command.
The dashboard follows your system's light or dark appearance and switches the logo with it.
Save goals in the sidebar and use Setup for optional model connections and new-campaign data options.
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
