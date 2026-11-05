# Run bounded research in any repository

Drill adopts the repeatable experiment workflow from [Karpathy's autoresearch](https://github.com/karpathy/autoresearch).
The human defines the research brief, editable source, fixed evaluator, and budget.
The agent proposes one committed experiment at a time.
Drill measures it, retains its evidence, and prepares the next experiment from the best accepted result.

The research contract is independent of language, dataset, hardware, and assistant provider.
Your evaluator determines what a valid improvement means for your project.
XOR is a separate product and is not required or invoked by this workflow.

## Configure a campaign

Set the campaign configuration version to 2 and add this section before creating a new campaign.
Older clients reject version 2 rather than silently ignoring the research restrictions.

```json
{
  "schema_version": 2,
  "research": {
    "brief": "Improve the supplied baseline without changing its evaluation rules.",
    "editable_paths": ["src/search.py"],
    "max_iterations": 5,
    "budget_seconds": 300
  }
}
```

The editable list names exact repository-relative files, including new files you intend to create.
Directories and wildcard expansion are not supported.
Characters such as brackets in a framework route name are treated literally by the core.
An assistant adapter may have stricter filename requirements for its own permission system.
Files outside that list, evaluator assets, the configuration, and adapter source are protected.
Symlinks and submodules cannot be editable source files.
Drill checks the full candidate against the campaign's initial commit before starting its evaluator.
An out-of-scope change produces an invalid receipt without a measurement.

The iteration budget limits each explicit run request.
Repeating the command starts another bounded request; it is not a lifetime campaign quota.
The time budget caps each local evaluator invocation, including startup.
It does not define the training duration or cancel an already submitted remote job.
A project evaluator must enforce its own training budget, identify hardware and data, and handle remote-job cancellation.
Keep those settings fixed in saved assets and the comparison context.

## Use your current agent

```sh
drill init --config research.json
drill baseline
drill run --iterations 5
```

The default command returns a research handoff for the agent already working with you.
It does not launch a provider or change that session's permissions.
The handoff names the managed checkout, instructions, brief, allowed files, and comparison result.
Commit one candidate there and evaluate it with `drill step` and a concrete hypothesis.
Call `drill run` again before the next candidate so Drill prepares the accepted starting point.
The agent must track the remaining iterations in the current handoff.

## Keep and discard without deleting history

New research campaigns use the existing named worker checkout under `.worktrees/drill/`.
When its tree differs from the incumbent, Drill creates a checkpoint commit containing the incumbent tree, with the current worker commit as its parent.
It then fast-forwards that owned branch to the checkpoint.
The rejected candidate remains reachable in Git and retains its receipt.

Dirty files, occupied paths, and ignored-file collisions are refused.
A pending evaluation must be resumed before that worker continues.
An interrupted agent invocation without a recorded outcome stops that worker rather than silently replaying it.
Inspect its retained request, logs, and checkout before choosing another named worker.
No reset, clean, force update, or automatic cleanup is performed.

## Restrict an unattended assistant

An optional coding-agent adapter can enforce its assistant's tool permissions.
The [OpenCode example](../examples/opencode/README.md) demonstrates a configurable launcher and restricted file editing.
Other assistants can implement the same [agent request and result contract](adapters.md).
There is no assistant registry or provider-specific mode in the core.

Candidate scope validation happens after an assistant edits files.
It prevents an out-of-scope candidate from entering evaluation, but cannot undo earlier filesystem or network effects from trusted code.
Assistant tool permissions are separate from operating-system process isolation and from plugin startup behavior.
Use a separately verified execution environment when stronger containment is needed.

## Existing campaigns

Only newly initialized campaigns with a saved research section use this workflow.
Campaigns without it retain their existing progression.
Existing campaign code, evaluation rules, and historical evidence are never upgraded in place.
Create a new campaign to adopt the research contract.

Drill continues to require a strict measured improvement.
Unlike the upstream instructions, an equally scoring simplification is not accepted automatically.
Any change to that acceptance policy needs a separate explicit design.
