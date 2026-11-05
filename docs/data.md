# Include submodules and large files

Drill uses local data first.
It never downloads missing dependencies unless the campaign configuration permits it.
The chosen settings become part of the campaign's saved configuration.

Add the following configuration when the evaluator needs submodules or Git LFS data.

```json
{
  "materialization": {
    "submodules": true,
    "lfs": true,
    "allow_network": false
  }
}
```

Merge that section into the normal campaign configuration alongside the objective and evaluator.
Leave either data option false when it is not needed.

## Submodules

A submodule points to another repository at one exact commit.
Drill reads the registration from the selected commit's `.gitmodules` file.
It searches the registered local object store and initialized local submodule checkout for that exact commit.
It snapshots the committed files recursively, even if the submodule's working checkout currently uses a newer commit.
It does not check out files or change the original repository.

Missing commits fail with downloads disabled.
With downloads explicitly allowed, Drill fetches into a temporary owned object store.
Relative submodule URLs resolve against the parent repository's origin.
For a local repository without an origin, they resolve against that repository's path.
Nested submodules follow the same policy.

## Git LFS

Git LFS stores a small pointer in Git and keeps the real data separately.
The pointer identifies the data by SHA-256 and size.
When LFS materialization is enabled, Drill finds the corresponding local LFS object and checks both values before copying it into the source snapshot.
It checks the copied hash again to catch changes during the copy.
The original checkout keeps its pointer or existing content unchanged.
Drill-created worker checkouts retain LFS pointers rather than downloading objects through Git LFS checkout filters.
This also applies when preparing the next experiment from the incumbent.
The explicit materialization settings control the evaluated snapshot, not an implicit worker download.
Create a new campaign to apply this worker-checkout behavior to an older saved runtime.

If an object is missing and downloads are allowed, Drill uses Git LFS in an owned temporary clone.
Git LFS must be installed and the original repository must have an origin remote.
Credentials remain the responsibility of the configured Git credential tools.
The temporary clone uses its own LFS cache.
Drill does not change global Git settings or fetch into the source repository's cache.

## Evidence and failure

The materialization result lists each submodule path and exact commit, and each LFS path, SHA-256, and size.
The normal source inventory then hashes the real snapshot bytes.
An unavailable commit, missing object, corrupt hash, wrong size, or escaping symlink cannot provide an evaluation score.
Existing frozen campaigns keep their original saved code and behavior.
Create a new campaign to enable these options.

## Unrelated repository data

Use the evaluator's [exact source selection](adapters.md#select-only-the-source-an-evaluator-needs) when an experiment needs only a few committed files.
This avoids acquiring unrelated models or submodules.
Selected data still requires the normal materialization options and verified bytes.
Freezing evaluator assets captures only the declared assets, independently of the evaluation source selection.
