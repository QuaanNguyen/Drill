<p align="center">
  <img src="assets/banner.svg" alt="Drill" width="100%">
</p>

Drill runs research experiments in a Git repository.
Connect an evaluator and a coding agent, then let Drill compare committed changes against the best accepted result.
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
Add a coding-agent adapter to use the automatic loop.
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
