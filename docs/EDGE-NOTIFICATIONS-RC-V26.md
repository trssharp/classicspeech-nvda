# ClassicSpeech — Edge Notifications 4.0.26 RC 1

## Purpose

ClassicSpeech RC v26 adds configurable Microsoft Edge UI Automation notifications. It keeps the existing Page Orientation presentation, same-synth Voice Profile routing, and native NVDA fallback behavior.

## Supported NVDA versions

- Minimum: NVDA 2025.1
- Last tested: NVDA 2026.1

## Microsoft Edge notifications

The new **NVDA menu → Preferences → ClassicSpeech → Web / Browse Mode Settings → Microsoft Edge Notifications** panel controls supported Edge UIA activity notifications.

- Each notification can be enabled or left to native NVDA speech.
- Use `F2` to set a replacement message for the focused item.
- Use `Delete` to restore the native message for the focused item.
- The checklist uses native checkbox state announcements; labels name only the notification.
- Unknown or malformed activity data fails open to native Edge behavior.
- Edge `Loading page` and `Loading complete` remain distinct. When ClassicSpeech Page Ready is enabled, the overlapping native completion notice is suppressed only for that exact completion event.

## Installation

1. Download the `.nvda-addon` file and its `.sha256` checksum sidecar.
2. Optionally compare the downloaded file’s SHA-256 with the sidecar.
3. Open the `.nvda-addon` file in Windows Explorer or activate it from your download location.
4. Approve the NVDA installation prompt.
5. Restart NVDA when prompted.

This is a release candidate. Keep a known-good add-on or configuration backup available while evaluating it.

## Verification completed

- Focused Edge routing and configuration harnesses passed.
- Full ClassicSpeech harness gate passed in GitHub Actions on the Edge branch.
- The package validates required runtime members, including `appModules/msedge.py`.
- Final confidence for Edge speech remains subject to live NVDA validation on the target machine.
