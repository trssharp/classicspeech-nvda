# ClassicSpeech Development Workflow

## Purpose

This document defines how ClassicSpeech work moves from an idea or report to a tested, date-named NVDA add-on build. The goal is deliberate, traceable work—not rapid changes directly in the active runtime.

## Source of truth and locations

| Purpose | Location |
| --- | --- |
| Active Git source | `C:\Users\trssh\Documents\development\nvda development\classicspeech-nvda` |
| Remote repository | `https://github.com/trssharp/classicspeech-nvda` |
| NVDA reference source | `C:\Users\trssh\Documents\development\nvda development\nvda master` |
| Installed test runtime | `C:\Users\trssh\AppData\Roaming\nvda\scratchpad\globalPlugins` |
| Historical snapshots | `C:\Users\trssh\Documents\development\nvda development\ClassicSpeech historical` after the legacy folder is renamed |

Do new work only in the active Git source. The scratchpad runtime is a deployment target, never the place to edit source. Historical snapshots are read-only comparison material.

## Branch policy

### Current policy: one stable branch plus short-lived work branches

- `main` is the current verified integration baseline.
- Do not make feature or bug-fix edits directly on `main`.
- Create one short-lived branch for one scoped item.
- Merge the branch only after automated checks and the relevant live NVDA checks pass.
- Delete the merged branch.

Use these names:

```text
feat/<short-description>
fix/<short-description>
docs/<short-description>
chore/<short-description>
research/<short-description>
```

Examples:

```text
feat/web-processor-load-boundary
fix/remote-profile-trigger-serialization
docs/installation-troubleshooting
research/browse-mode-speech-sequences
```

### When to add `dev`

Do not create a permanent `dev` branch merely because it is common elsewhere. Add it when one of these is true:

- two or more substantial changes must be integrated at once;
- other contributors begin opening pull requests regularly;
- `main` becomes public and must stay a particularly conservative release-candidate baseline.

At that point use:

```text
feature/fix branch → dev → live RC validation → main → dated release
```

## Intake: classify every item before coding

Every request begins as one of these types:

| Type | Meaning | Typical output |
| --- | --- | --- |
| Bug | Existing behavior is wrong or regressed | Reproduction, regression test, focused fix |
| Feature | New user-visible capability | Scope, design, tests, docs, implementation |
| Research | A question must be answered before deciding | Evidence note and recommendation; no behavior change yet |
| Chore | Tooling, packaging, CI, docs, cleanup | Narrow maintenance change |
| Release | A validated baseline is packaged for testers | Date-named add-on, SHA-256, release notes |

For any item, record:

1. the user problem or desired outcome;
2. exact reproduction steps or an example speech sequence, where relevant;
3. expected versus current behavior;
4. affected NVDA version, Windows version, synthesizer, voice/variant, and ClassicSpeech profile when relevant;
5. explicit non-goals.

## Required planning before implementation

Before changing behavior, write a concise implementation plan in `.hermes/plans/` or a tracked `docs/plans/` document when it is useful to other contributors.

A plan must answer:

1. What problem are we solving?
2. What will not change?
3. Which source files and NVDA APIs are involved?
4. Which existing behavior is the baseline to preserve?
5. What regression test fails before the fix?
6. What harness and live NVDA checks prove success?
7. What risks or rollback path exist?

Research items end with a recommendation before any feature branch is created. Do not convert an uncertain theory into a code change without evidence.

## Implementation loop

1. Start from clean, current `main`.

   ```bash
   git switch main
   git pull --ff-only
   git switch -c fix/short-description
   ```

2. Add or update the smallest relevant harness first.
3. Run the harness and confirm it fails for the expected reason when adding a regression test.
4. Make the smallest implementation change that satisfies the plan.
5. Run focused checks, then the full harness gate.
6. Inspect the diff before committing.

   ```bash
   git diff --check
   git diff
   git status --short
   ```

7. Commit a single coherent change.

   ```bash
   git add <intended-files>
   git commit -m "fix: short description"
   ```

8. Push the branch and open a pull request into `main`.
9. Review the pull-request diff and wait for GitHub Actions.
10. Deploy that verified branch to scratchpad only when live NVDA testing is needed.

## Verification ladder

A green GitHub check is necessary but not sufficient for ClassicSpeech.

| Layer | Required evidence |
| --- | --- |
| Source | Python compilation and relevant focused harness |
| Regression | Full harness gate passes |
| CI | GitHub Actions succeeds and creates dated package + checksum |
| Package | Manifest, archive layout, and SHA-256 are checked |
| Runtime | Source/runtime comparison after scratchpad deployment |
| Live NVDA | Relevant user path works in NVDA with the intended synth/profile |

For changes involving Voice Profiles, System notifications, Remote, Review, Keyboard, or a specific synthesizer, include explicit live checks for that route. Do not claim a live behavior is fixed from unit tests alone.

## Scratchpad deployment rule

Only deploy from a reviewed branch after source and automated checks pass. Always:

1. create a timestamped backup of the existing scratchpad plugin;
2. copy the complete verified source tree;
3. remove Python caches;
4. compile the deployed runtime;
5. compare source and runtime;
6. reload or restart NVDA as appropriate;
7. record the backup path and the live result.

Never edit files under `scratchpad\globalPlugins` as the primary source change.

## Merge and release rule

Merge to `main` only when:

- the scoped plan is satisfied;
- the relevant full automated gate passes locally and in GitHub Actions;
- required live NVDA validation is complete;
- documentation and release notes are updated when user-visible behavior changed.

Use the creation date for tested packages:

```text
ClassicSpeech-YYYY-MM-DD.nvda-addon
ClassicSpeech-YYYY-MM-DD.nvda-addon.sha256
```

If more than one release-quality build is needed on one day, retain the date-based package name from CI and distinguish the GitHub release/tag description with a short suffix such as `2026-07-20-02`.

## Fast path for tiny documentation changes

A documentation-only correction may use a `docs/` branch and skip live NVDA testing, but it still requires:

- review of the rendered Markdown;
- `git diff --check`;
- GitHub Actions success;
- a clear, focused commit.

## Safety rules

- Never delete or overwrite historical ClassicSpeech snapshots without explicit approval.
- Never delete `sequence_merger.py` without explicit approval.
- Never automatically switch the active NVDA synthesizer.
- Keep same-synth Voice Profile settings limited to driver-supported public settings.
- Preserve native NVDA behavior outside the explicitly owned ClassicSpeech speech route.
- Do not include private logs, personal NVDA configuration, credentials, or backups in Git commits or issue reports.
