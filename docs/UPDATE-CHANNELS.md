# Stable and development updates

## Users

Advanced settings expose **Check for updates automatically:** (checked by default)
and **Update from:** (`stable`, the default, or `dev`). Both manual and automatic
lookups use that preference. Clearing the checkbox stops automatic checks only.
The existing 30-second startup delay and once-daily successful-check throttle
remain. Apply/OK accept edits; Cancel/Close restore the latest accepted baseline.
Selecting a preference does not install a package.

Stable uses GitHub's latest regular release; drafts and prereleases are rejected.
Development uses paginated public GitHub Releases, not Actions artifacts, tokens,
or proxies. Only the official repository's prereleases with tags
`dev-YYYYMMDD.RUN` and both `ClassicSpeech-YYYYMMDD.RUN.nvda-addon` and its
`.nvda-addon.sha256` sidecar qualify. An empty channel reports **No development
release has been published yet.** No fallback to stable occurs.

Within the installed channel, only newer numeric versions are offered. To change
channels, accept the preference and explicitly run **Check for Updates...**.
The channel-switch confirmation names both versions and warns that returning
from a date-version development build to stable (for example 2.0) can install a
numerically lower version. Automatic checks never switch channels or install.
Download and NVDA installation/compatibility confirmation still require consent.

New packages embed `globalPlugins/_speech_core/build_info.json` with installed
channel, manifest version and source commit. This is not the user's preference.
Ordinary unlabelled-channel date/run verification builds are `unknown`, not dev.
Legacy short numeric releases are treated as stable; legacy date/run builds are
unknown and may transition only manually. Equal versions are not offered again.
Do not republish changed content under an existing version/tag.

## Maintainers: explicit publication only

`.github/workflows/publish-dev.yml` has **only** `workflow_dispatch`. It must stay
manual: no push, schedule, pull-request, workflow-run or reusable-workflow trigger.
The separate `verify-dev.yml` runs tests/packages on dev and the updater feature
branch, but has read-only permissions and cannot publish releases.
The existing stable `verify-and-package.yml` is unchanged.

The manual publisher is registered on the default branch, `main` (workflow-only
enablement `e53860e`). Dispatch **main**, supplying the reviewed full dev SHA;
main's workflow validates and checks out that SHA explicitly. Its build scripts,
notes and runtime all come from the pinned dev checkout, not main. The dev-branch
workflow retains its dev-dispatch guard; do not copy it wholesale over main's
adapted workflow.

**Rolling-notes alignment:** main's enabled publisher initially writes only a
build/commit warning. After this rolling-notes feature reaches dev, a separate,
authorized workflow-only change on main must replace that notes-generation line
with `python -m scripts.dev_release_notes --version "$version" --commit "$COMMIT"
--output release-assets/notes.md` (one shell line). Keep main's dispatch guards,
pinned checkout and commit-based artifact names unchanged. Until that follow-up
lands, the registered main workflow does not include the rolling What's new in
its GitHub release body. Registration itself is no longer blocked.

For an explicitly approved publication:

1. Review the exact trusted `dev` head and its verification results. Record its
   full 40-character SHA. The active workflow refuses forks and dispatches outside main.
2. Manually run **Publish development prerelease (manual only)** with branch
   `main` and input `commit` equal to that full dev SHA. CLI equivalent:
   `gh workflow run publish-dev.yml --ref main -f commit=FULL_40_CHARACTER_SHA`.
   This command publishes a release; do not run it for ordinary CI verification.
3. The read-only job validates the full input SHA against the current remote
   dev head, checks out that SHA and confirms HEAD agrees, runs every `tests/*harness.py` through `scripts/verify.py`,
   and packages that exact commit. Both development verification and publication
   use the same discovery-based verifier; the stable workflow also discovers the
   same harness glob instead of a separate hand-maintained test list.
4. UTC date and this workflow's run number generate one numeric manifest version
   and a unique `dev-` tag. The package records `dev` plus the full commit. Public
   assets contain the add-on and checksum. After the main-workflow alignment above,
   notes identify the version and source commit, warn that the build is experimental,
   and include the same [rolling What's new](DEVELOPMENT.md) as the package manifest.
   Both read the notes from the pinned checkout using the same parser; later edits
   to dev cannot change a published version's notes. Stable notes and default
   verification packaging remain unchanged.
5. Only the publication job has `contents: write`. It consumes this run's
   verified artifact, checks the checksum, rechecks the current dev head, creates
   the immutable tag at the verified commit, and publishes with prerelease true,
   draft false, and make-latest false. It reads back the release and asset names.
6. Inspect the resulting release and anonymously download/verify both assets.
   Never replace an existing tag or asset. If a failed publication leaves a tag,
   diagnose it; start a fresh manually reviewed run rather than deleting the tag
   or automatically retrying publication. No automatic stable release is made.

The package is not deployed or installed by CI. Tests use network mocks and do
not replace a live NVDA accessibility/keyboard check. No workflow dispatch or
release publication is required to verify this implementation locally or in CI.
