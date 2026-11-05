# Drill research

Drill compares committed experiments under saved evaluation rules.
Its language separates measured improvement from publication and model qualification.

## Language

**Campaign**:
A research study with saved evaluation rules, starting source, and experiment history.
_Avoid_: Session, project

**Baseline**:
The first passing measurement of a campaign's starting source.
_Avoid_: Incumbent

**Attempt**:
One committed candidate and its hypothesis, measurement, decision, and retained evidence.
_Avoid_: Iteration result

**Incumbent**:
The best accepted result under the campaign's comparison rules.
_Avoid_: Latest commit, baseline

**Worker**:
A named owner of one research checkout and branch within the project repository.
_Avoid_: Agent session

**Checkpoint**:
A preserved starting point for the next experiment that retains the worker's earlier work.
_Avoid_: Reset, discarded history

**Research brief**:
The human-owned goal, editable source scope, and experiment budget saved with a campaign.
_Avoid_: Permission policy

**Candidate scope**:
The exact source files that a campaign permits an experiment to change.
_Avoid_: Process isolation, tool permissions

**Evaluator adapter**:
The project-specific measurement implementation for a supplied candidate.
_Avoid_: Model judge

**Coding-agent adapter**:
The implementation that invokes a caller-selected assistant to edit a worker.
_Avoid_: Model conversation

**Current-agent handoff**:
Research context supplied to the assistant already working with the user.
_Avoid_: Automatically launched assistant
