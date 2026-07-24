# ClassicSpeech versioning and CI artifact identity

## Generated numeric version

Every GitHub Actions workflow run generates the package manifest version:

```text
YYYYMMDD.RUN
```

For example, workflow run 16 on UTC date 2026-07-24 installs as version:

```text
20260724.16
```

The source `manifest.ini` deliberately uses the neutral `0.0.0` placeholder. During packaging, `scripts/package_addon.py` replaces that value **inside the `.nvda-addon` archive only**. The checked-out source manifest is never changed.

This uses two numeric components because current NVDA Add-on Store logic compares side-loaded add-on versions only when it can parse two or three integers. The date component preserves chronological order; the GitHub Actions run component makes every workflow artifact unique, including multiple runs on one day.

## Artifact names

An artifact includes the generated installed version and the source commit:

```text
ClassicSpeech-20260724.16-gddf21ae.nvda-addon
```

- `20260724.16` is the version shown by NVDA after installation.
- `gddf21ae` identifies the source commit used by the workflow.
- The `.sha256` sidecar has the same basename.

Git tags and GitHub releases may still carry human-facing labels such as `RC` or `stable`, but they do not change the numeric installed version.

## Release builds

For an official release, run the workflow manually and fill in **Release version** with a numeric version such as `4.0.0` or `4.0.1`. That value is written into the package manifest and its artifact name is simply:

```text
ClassicSpeech-4.0.0.nvda-addon
```

Leave **Release version** blank for all ordinary branch, pull-request, and manual test builds. Those continue to use the generated UTC-date-and-run version.
