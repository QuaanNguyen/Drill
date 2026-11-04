# XOR native evidence example

This adapter compares completed XOR native evidence from a frozen, human-verified blind evaluation on one Mac.
It does not train a model or run inference.
It runs the repository's pinned `checker-promotion.js` and keeps its full decision as an artifact.
The objective is lower median native latency, with every native replacement check required for candidates.
A model that only becomes smaller can pass XOR's replacement checks and still fail this campaign's latency objective.

Missing native evidence produces an inconclusive attempt without a score.
A smoke test, generated labels, or an incomplete summary cannot replace the required evidence.

## Preparation

Use a separate research branch or copy of XOR and Python 3.11.8 or later, Git, and Node.js.
The adapter itself uses only the Python standard library and Node.js standard library.
Leave the existing XOR checkout and historical receipts unchanged.

Complete the native evaluation and human review workflow before preparing a campaign.
Read XOR's `docs/checker-training.md` and `xor/prototype/evaluate-checker-native.js` for the current requirements.
Run the native evaluator on the same Mac with the exact registered runner and models.
Preserve the full evidence including original responses and every measured repetition.

Commit these files in the target research repository before initialization:

| Path | Required contents |
| --- | --- |
| `xor/prototype/checker-promotion.js` | The authoritative XOR replacement checker. |
| `xor/prototype/evaluate-checker-native.js` | The exact source that produced both native evidence files. |
| `research/native-runner` | The exact runner bytes used for both measurements. |
| `research/requests.jsonl` | The exact frozen V3 requests, in their original order, including IDs, input hashes, and expected decisions. |
| `research/qualification.json` | The reviewed qualification registration described below. |
| `research/reference.json` | Full completed native evidence for the registered original model. |
| `research/evidence.json` | Initially an exact copy of the original native evidence. |
| `research/model.bin` | Initially the registered original model bytes. |

The qualification registration must contain `blind`, `humanVerified`, and `coverageComplete` set to true only when those claims have independently been established.
It must also contain the original model's SHA-256 as `originalModelSha256`, the exact request file's SHA-256 as `frozenEvaluationSha256`, and every case ID in order as `caseIds`.
The registration is an explicit trust input, and setting its flags does not perform or prove the underlying review.
This example intentionally provides no ready-made qualification registration or model score.

The runner, request file, original evidence, qualification registration, and native source files are copied from the initial Git commit into the campaign's frozen assets.
The adapter checks model bytes against the committed candidate model and runner bytes against the frozen runner.
Committing real model and runner binaries can make the research repository large.
Git LFS pointer files do not satisfy the model and runner byte checks.
Enable LFS materialization and provide verified local objects or explicitly allow downloads before initializing such a campaign.
Do not expose private evaluation requests through a public repository.

## Campaign

Run these commands from the Drill repository after replacing `/path/to/xor-research` with the prepared repository:

```sh
python3 hub.py init --repo /path/to/xor-research --config examples/xor/config.json --campaign xor-native
python3 hub.py baseline --repo /path/to/xor-research --campaign xor-native
python3 hub.py workspace --repo /path/to/xor-research --campaign xor-native --worker candidate-a
```

The baseline accepts only the exact frozen original evidence, verifies all evidence requirements, and records its actual measured latency.
The baseline artifact still reports that replacing the original with itself has no native improvement.
The replacement metric remains zero while a separate metric records baseline readiness.
No artificial size reduction or speedup is used to manufacture a passing baseline.

In the managed candidate workspace, replace `research/model.bin` with the candidate and `research/evidence.json` with its full completed native evaluation.
Keep the frozen requests, original, runner, machine, native evaluator source, request format, and measurement settings identical.
Commit the candidate files before evaluating them:

```sh
python3 hub.py step --repo /path/to/xor-research --campaign xor-native --worker candidate-a --hypothesis 'The new model reduces native Mac latency while preserving the original decisions.'
python3 hub.py dashboard --repo /path/to/xor-research --campaign xor-native
```

The native checker always compares candidates to the registered original, while the hub additionally requires latency improvement over its latest accepted candidate.
The hub's comparison context includes the actual dataset digest, runner and native evaluator digests, machine identity, request format, and complete measurement settings.
An unchanged original model is rejected as replacement evidence even if it is remeasured with lower timings.

## Evidence and limits

Complete responses retain candidate evidence, original evidence, qualification registration, and native promotion results as relative artifact paths.
They report median and 95th percentile latency, deployment bytes, correct decisions, harmful approvals, ordinary denials, and missed confirmations.
The adapter requires every registered case, exact input hashes and labels, successful direct responses without reasoning, and three finite positive timings per case.
It conservatively requires the native evaluator's current token limit, timeout, repetition count, and warmup count.
Incomplete evidence cannot create a baseline or supply an incumbent score.

This is an evidence importer with a trusted local adapter, rather than an independent witness of the original native execution.
Recorded responses, timings, human review, blindness, and machine identity must come from a trusted evaluation process.
The hub cannot prove those claims from JSON alone.
Timings are imported as point measurements, so this example does not establish a statistical confidence interval or account for repeated benchmarking noise.
An accepted campaign result does not publish XOR, change its download metadata, or replace its own model qualification and release process.

## Installation and adapter verification

The included tests use explicitly synthetic evidence to verify plumbing and rejection behavior.
Their measurements do not evaluate or qualify any model.
Point `XOR_REPO` at a local XOR checkout to run the subprocess tests against its actual replacement checker:

```sh
XOR_REPO=/path/to/xor python3 -m unittest discover -s examples/xor -p 'test_*.py' -v
```
