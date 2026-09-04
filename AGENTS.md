# ClassicSpeech for NVDA — Agent Guide

## Scope and source of truth

- Active repository: `classicspeech-nvda`.
- Project roadmap/spec: `../spec.docx`.
- New work belongs in this repository, on a focused Git branch from `main`.
- Do not create independent repository copies, branch-named source folders, or a new `vNN` source folder for ordinary feature work. The historical/versioned folders outside this repository are reference material, not active workspaces.
- Use a separate managed Git worktree only when explicitly needed for a long-lived parallel experiment or comparison.
- After a pull request is merged, remove its temporary worktree and delete its unneeded local branch. Run `git worktree list` first so an active worktree is never removed accidentally.
- Preserve important build artifacts through GitHub Releases or `Classic Speech Historical` before removing a worktree. Generated `dist` output is not source history.

## Delivery boundaries

- ClassicSpeech is an NVDA add-on. Do not modify NVDA core or the installed NVDA baseline unless Tim explicitly requests a separately scoped NVDA-core experiment.
- Keep changes narrow and preserve native NVDA behavior unless the specification explicitly changes it.
- Preserve native literal/review/caret/Say All behavior. Do not route ordinary document text through ClassicSpeech processing without a defined, tested requirement.
- The token editor owns speech-token ordering and placement. Text Processing owns reporting/filtering transformations; do not move token-placement policy into it.
- `sequence_merger.py` was removed after an audit confirmed it had no active dependents. Do not reintroduce sequence-merging behavior without a defined, tested requirement.

## Accessibility and settings

- The target user is visually impaired. Prefer native NVDA controls, keyboard-complete workflows, stable labels, and screen-reader-friendly feedback.
- Follow existing settings-dialog transaction behavior: Apply, OK, Cancel, Close, reload, and external configuration save must leave persisted and runtime state coherent.
- Do not replace an NVDA accessibility-enhanced control with a raw wx equivalent without explicit approval.

## Validation

- Read the relevant specification and trace existing code/tests before editing.
- Add or extend focused harness coverage before changing subtle speech-filter, settings, or routing behavior.
- At minimum, compile changed Python files and run the relevant project harnesses/tests.
- Static tests do not prove speech behavior: clearly distinguish them from a live NVDA validation. Never restart NVDA automatically.
- Before a release candidate, run the project packaging and archive-member checks; report the exact output path and checksum.

## Scratchpad and live validation

- Work in the Git checkout, not directly in the NVDA scratchpad.
- Deploy to scratchpad only when Tim explicitly requests a working/runtime build. Make a timestamped backup, compare source with deployed files, compile the deployed entry points, and do not restart NVDA automatically.
- Preserve the installed NVDA baseline. Scratchpad testing and installed-add-on testing must not be mixed in one trial.

## Git hygiene

- Check `git status` and the active branch before editing.
- Do not commit, push, rebase, force-push, or rewrite history unless Tim explicitly requests it.
- Keep unrelated working-tree changes untouched and report them separately.
- Do not place secrets, logs, runtime backups, or generated artifacts under version control.

## Information placement

- Put stable, repository-specific rules in this file.
- Put reusable cross-project procedures in a Hermes skill.
- Keep personal preferences, account details, and temporary task state out of this repository.
