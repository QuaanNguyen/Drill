# Portable research workflow

## Existing ownership

The campaign saves its runtime, configuration, evaluator, and evidence.
The workspace module owns named Git branches and checkout locations.
The evaluator adapter owns project measurements and qualification rules.
The optional agent adapter owns assistant invocation.
A plain model conversation is not a coding-agent implementation.

## Chosen contract

New research campaigns require configuration schema version 2 so older clients refuse them instead of ignoring restrictions.
The request and result wire schema stays at version 1.
A new optional research section contains a brief, an exact list of editable repository files, a maximum iteration count, and an evaluator invocation time budget.
The current repository agent remains the default.
No provider, product, machine path, GPU, language, or data format belongs in this section.

The campaign module validates candidate changes against the starting commit before invoking the evaluator.
Protected files, renames out of scope, symlinks, and gitlinks cannot become valid research candidates.
The research request supplies the brief, editable files, budget, and selected incumbent to either execution mode.

Before each experiment, an owned clean worker returns to the incumbent tree through a new checkpoint commit followed by a fast-forward merge.
The checkpoint retains the rejected commit as its parent.
No reset, clean, force update, or deletion is used.
Existing edits, ignored-file collisions, pending evaluations, and interrupted attempts cause a refusal rather than automatic cleanup.

An optional OpenCode adapter uses a configurable launcher, defaulting to ordinary OpenCode.
It permits necessary file reads and exact scoped edits, denies shell/network/delegation and other tool actions, and leaves committing and evaluation to trusted host code.
It does not import XOR, select ASU, or change global assistant settings.
A launcher such as opencode-asu is a user-selected executable, not a core mode.

## Alternatives and synthesis

Two independent design candidates compared a stable owned worker with immutable per-iteration worktrees.
Immutable worktrees make starting points structural but add a second workspace ownership scheme and accumulate checkouts.
The stable worker design was selected because checkpoint commits preserve every rejected candidate while keeping the existing branch and checkout interface.
The strongest part of the alternate design was retained: exact scope validation belongs in the campaign and applies to manual evaluations as well as automatic loops.

The organizing structures are the normalized research configuration, campaign receipts, and existing worker identity.
The research module owns validation and progression helpers, rather than spreading assistant-specific rules across commands.
Tests cross the same command and adapter interfaces that users call.

## Trust and compatibility

Candidate validation occurs after editing and is not process containment.
Assistant permissions constrain model tools, not arbitrary plugin initialization or trusted adapter code.
A generic command adapter remains trusted executable code.
Remote evaluators remain responsible for remote job duration and cancellation.

Research behavior activates only when the saved configuration contains the new research section.
Older campaigns keep their frozen code and behavior.
Unattended approval policy is confined to an explicit optional adapter; the client never changes the surrounding session's approvals.

## Workflow and verification

Rigor is high because unattended editing crosses tool permissions, worker ownership, and retained evidence.
The playbook captured old command behavior, compared two designs, implemented the provider-neutral contract, verified the optional adapter, and ran independent reviews before publication.
Foundational Thinking put the saved research contract before assistant integration.
Laziness Protocol kept provider choices in one optional adapter instead of adding a core assistant framework.
Prove It Works required real allowed and denied tool calls, complete campaign flows, and an old-client refusal check.

The final core verifier passed 75 tests and eight synthetic XOR evaluator tests.
Both ordinary OpenCode and a caller-selected ASU wrapper completed a generated baseline, restricted edit, host commit, and accepted evaluation without a model override.
These are workflow checks, not training or model qualification.
The [captured proof](../proofs/universal-research.json) records the executed checks and source hashes.
Independent core and final adapter reviews found no remaining source blockers after the recorded fixes.
Reviewers inherited the session model as required by the user's profile; model diversity was reduced.
