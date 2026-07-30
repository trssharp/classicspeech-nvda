# Page Orientation Presentation Research Plan

> **Status: archived research, not an active implementation plan.** No ClassicSpeech runtime patch was shipped from this research. The supported add-on API cannot mutate virtual-buffer content or insert synthetic structural lines. Any future work would require a separately approved NVDA-core design; do not use the remaining historical investigation steps as implementation authorization.

**Goal:** Determine whether an explicit, opt-in ClassicSpeech Page Orientation mode can preserve NVDA Browse Mode buffer loading, focus handling, caret initialization, braille/vision updates, and user-selected Auto Say All behavior while replacing only the initial root-document/title and first-line presentation with one concise ClassicSpeech page summary.

**Architecture:** Firefox, Chromium, and other Browse Mode virtual-buffer backends arrive at NVDA's shared `BrowseModeDocumentTreeInterceptor.event_treeInterceptor_gainFocus` presentation method only after their backend-specific virtual buffer has been selected. The implementation target is that common post-backend page-entry seam, not a browser-name allowlist. A normal ClassicSpeech opt-in, version-guarded, identity-scoped runtime wrapper must preserve native setup and replace presentation only for a current, ready Browse Mode virtual buffer. It must restore the original method on add-on termination/reload and fail closed to NVDA-native behavior on any incompatibility; it must not filter final text by words such as `busy`, title text, or document content.

**Tech stack:** ClassicSpeech research branch; released NVDA used by Tim; local NVDA reference checkout at `C:\Users\trssh\Documents\development\nvda development\nvda master`; Firefox; a Chromium browser such as Edge or Chrome; NVDA log with personal data redacted before storage.

---

## Product intent to investigate

The desired interaction is:

```text
User activates a link, browser address bar, or other navigation command
→ NVDA creates and readies the normal virtual buffer
→ NVDA keeps normal focus and initial Browse Mode caret placement
→ ClassicSpeech speaks one concise page-orientation summary
→ NVDA does not additionally speak the initial document title/root object and first line
```

The research must establish whether the mode can deliver that interaction without changing unrelated page events, forms, alerts, live regions, later focus changes, refresh behavior, or browser-specific loading semantics.

## Verified starting facts

These facts are verified against the local NVDA reference source and must be rechecked against the released NVDA build before implementation.

1. Shared initial Browse Mode presentation is in `source/browseMode.py`, `BrowseModeDocumentTreeInterceptor.event_treeInterceptor_gainFocus`.
2. On a first focus gain, that method calls `event_gainFocus`, initializes the Browse Mode selection/caret when not in focus mode, records the document identifier, reads `virtualBuffers.autoSayAllOnPageLoad`, and marks first gain focus complete before it chooses the presentation branch.
4. With Auto Say All enabled, the same method speaks root document properties and starts Say All.
5. With Auto Say All disabled, the same method speaks the root document and then speaks the initial selected line (or preselected text).
6. In the inspected current source, the nested first-entry `event_gainFocus` call returns without emitting root-document focus speech when the focus object is `rootNVDAObject` and Browse Mode is active. That confirms the explicit later presentation branch is the target for title/root and initial-line replacement; it does not make the focus/caret setup disposable.
7. The method then performs `reportPassThrough` and `braille.handler.handleGainFocus`.
8. Firefox's read-only document selects `virtualBuffers.gecko_ia2.Gecko_ia2` in `source/NVDAObjects/IAccessible/mozilla.py`.
9. Current Chromium source selects `ChromeVBuf` in `source/NVDAObjects/IAccessible/chromium.py`, subject to its existing busy-state virtual-buffer rule. This is an IA2 Chromium path in the inspected source; do not assume a generic UIA route without runtime confirmation.
10. `VirtualBuffer.event_documentLoadComplete` can call the same shared initial-focus method when early focus arrived before the buffer was ready.

## Non-goals

- No generic speech-sequence text filtering.
- No suppression keyed to literal title, `document`, `busy`, or first-line text.
- No change to virtual-buffer construction, browser backend selection, `isReady`, document-load timing, caret placement, selection, Browse/Focus mode, braille, vision, or ordinary page navigation.
- No changes to Firefox Busy-state diagnostics or suppression during this research.
- No implementation, scratchpad deployment, package, or release before Tim explicitly accepts a design after the evidence review.

## Safety hypothesis

A future implementation may be viable only if all of the following are true:

1. It acts only for a newly focused, current Browse Mode document owned by the enabled orientation mode.
2. It lets the original handler retain its focus-event and selection/caret initialization path.
3. It chooses a structured presentation replacement before the root/title/first-line calls are emitted, rather than deleting final strings after they have lost provenance.
4. It reuses NVDA's existing `virtualBuffers.autoSayAllOnPageLoad` preference, which ClassicSpeech already exposes as `Automatic Say All on page load` in Web / Browse Mode Settings. The future mode always speaks the summary first, then starts NVDA Say All from the already-initialized caret only when that native preference is enabled.
5. It fails closed to NVDA-native behavior on a version/signature mismatch, missing document identity, focus mode, nested speech, or any unexpected backend state.
6. It restores all patched methods by exact identity on add-on termination/reload if a runtime experiment is ever approved.

---

## Task 1: Establish the exact backend-to-presentation call maps

**Objective:** Document the actual released-NVDA paths from Firefox and Chromium document objects to the shared initial Browse Mode presentation method.

**Files to inspect:**
- NVDA reference: `source/NVDAObjects/IAccessible/mozilla.py`
- NVDA reference: `source/virtualBuffers/gecko_ia2.py`
- NVDA reference: `source/NVDAObjects/IAccessible/chromium.py`
- NVDA reference: the module defining `ChromeVBuf`
- NVDA reference: `source/virtualBuffers/__init__.py`
- NVDA reference: `source/browseMode.py`
- Released NVDA source/runtime matching the installed test version.

**Steps:**

1. Record the Firefox document class, selected tree-interceptor class, virtual-buffer superclass chain, and every route that reaches `event_treeInterceptor_gainFocus`.
2. Record the Chromium document class, selected tree-interceptor class, busy-state eligibility conditions, virtual-buffer superclass chain, and every route that reaches the same method.
3. Identify whether Edge and Chrome use the same document/virtual-buffer classes in the released NVDA build used for live testing.
4. Identify refresh and delayed `documentLoadComplete` paths separately from first navigation.
5. Write a compact backend comparison table in a redacted research note; include source file, class, method, trigger, and whether it can invoke initial root/line presentation.

**Acceptance evidence:** A source-backed map shows common versus backend-specific behavior without assuming Firefox and Chromium have identical loading timing.

## Task 2: Separate state setup from presentation in the shared handler

**Objective:** Identify the exact operations that must remain native and the exact calls that create the speech the proposed mode wants to replace.

**Files to inspect:**
- NVDA reference: `source/browseMode.py`, `BrowseModeDocumentTreeInterceptor.event_treeInterceptor_gainFocus`
- NVDA reference: `source/browseMode.py`, `event_gainFocus`, selection/caret helpers, and any relevant override points.
- NVDA reference: speech, braille, vision, and Say All APIs called by the method.

**Steps:**

1. Make a line-level table with two columns:
   - **Must preserve:** focus event dispatch, initial selection/caret setup, document identifier update, pass-through reporting, braille/vision behavior, and native error handling.
   - **Candidate presentation only:** root-object properties, root-object focus speech, initial-line/preselected-text speech, and the Auto Say All start decision.
2. Verify whether `event_gainFocus` itself can speak content relevant to a page entry. If it can, identify whether a replacement policy must preserve or deliberately own that presentation too.
3. Verify the order and behavior of `braille.handler.handleGainFocus` and any vision updates so a speech replacement cannot accidentally suppress non-speech feedback.
4. Identify whether the shared handler exposes a public extension point. If it does not, explicitly classify a ClassicSpeech runtime wrapper as private-API dependent and an NVDA-core seam as structurally safer.

**Acceptance evidence:** The plan identifies a possible structured replacement boundary and rejects final-text filtering as insufficiently scoped.

## Task 3: Reuse NVDA's existing Auto Say All preference

**Objective:** Define one clear presentation policy without duplicating a native NVDA setting.

**Established policy:**

```text
Page Orientation mode disabled:
    Preserve NVDA's existing page-entry presentation exactly.

Page Orientation mode enabled:
    Speak the ready-page ClassicSpeech summary.
    If NVDA's existing Automatic Say All on page load setting is enabled:
        start native Say All from the already-initialized caret.
    Otherwise:
        stop after the summary.
```

**Existing native control:** ClassicSpeech already exposes NVDA's `virtualBuffers.autoSayAllOnPageLoad` in **Web / Browse Mode Settings** as:

```text
Automatic Say All on page load
```

This remains the sole owner of the Auto Say All preference. The Page Orientation feature must read it at presentation time and must not create a second ClassicSpeech copy, override it, or silently alter it.

**Steps:**

1. Confirm on the released NVDA version that the existing checkbox writes the exact `virtualBuffers.autoSayAllOnPageLoad` value consumed by the shared initial Browse Mode handler.
2. Confirm that starting `sayAll.SayAllHandler.readText(CURSOR.CARET)` after the summary uses the caret already initialized by the preserved native setup path.
3. Confirm the summary's calculation and speech queue ordering. The summary must finish queuing before Say All starts, must not be cancelled by Say All, and must not delay page readiness or block UI responsiveness. Do not assume the existing delayed automatic-summary callback can be reused unchanged.
4. Define the future orientation-mode setting separately from Auto Say All. Its only responsibility is whether the initial root/title and first-line presentation is replaced by the summary. Default remains native NVDA presentation.
5. Define fail-closed behavior: a missing/invalid native setting, no ready buffer, focus mode, stale document, or incompatible NVDA method signature leaves the original NVDA presentation untouched.

**Acceptance evidence:** With Page Orientation mode enabled, Auto Say All off yields summary only; Auto Say All on yields summary followed by Say All. With Page Orientation mode disabled, both cases retain native NVDA behavior unchanged.

## Task 4: Design an observational, no-behavior-change live evidence matrix

**Objective:** Capture the real native sequence and timing before any suppression/replacement experiment.

**Preconditions:**

- Confirm the installed NVDA version, ClassicSpeech branch, Firefox/Chromium versions, configuration path, and log path.
- Use non-sensitive public pages or a local fixture. Do not commit raw URLs, titles, page content, credentials, or logs.
- Keep the released Automatic Page Summary option both off and on in separate runs.
- Do not deploy a runtime speech-replacement patch for this task.

**Matrix:**

For Firefox and a Chromium browser, run each combination:

1. New navigation from the address bar.
2. Activating an ordinary link.
3. Reloading the page.
4. Navigating away before a deliberately slow page settles.
5. Auto Say All off.
6. Auto Say All on.
7. Automatic Page Summary off.
8. Automatic Page Summary on.

For each run, record in a redacted note:

- event sequence and monotonic timestamps where available;
- native spoken order: root/title, initial line, Say All, loading/refresh messages, and Automatic Page Summary;
- focus object identity and tree-interceptor identity before/after;
- Browse Mode selection/caret position before/after;
- `isLoading`, `isReady`, and `passThrough` transition evidence where safely observable;
- whether the same shared initial-focus handler is reached once or multiple times;
- differences between Firefox and Chromium that are backend timing rather than defects.

**Stop conditions:** Any finding that root/title or initial-line speech is intertwined with a required focus/caret/braille/vision side effect invalidates a direct add-on replacement design until a safer core seam is designed.

## Task 5: Write a design decision record

**Objective:** Turn evidence into one of three explicit next steps.

**Possible outcomes:**

1. **Do not proceed:** native initial presentation cannot be safely separated on released NVDA, or live behavior is too variable.
2. **ClassicSpeech runtime experiment:** the sole implementation route. It remains an ordinary ClassicSpeech add-on feature—opt-in, version-guarded, one-shot scoped, reload-safe, and validated on the released NVDA version—not merely NVDA master. It must restore the original method by identity at add-on termination and fall back completely to native presentation on any mismatch.

**Decision record must include:**

- selected product policy from Task 3;
- exact backend coverage;
- chosen seam and why it preserves state setup;
- a fail-closed compatibility rule;
- required harnesses and live regression matrix;
- rollback method;
- explicit statement that Firefox Busy suppression remains a separate issue.

## Required verification before any implementation proposal

- Source map complete for Firefox and Chromium on the released NVDA version.
- Live evidence matrix completed with sensitive data redacted.
- Page Summary remains once-per-ready-current-document and does not move focus/caret.
- Native behavior is byte-for-byte/sequence-equivalent whenever the future mode is disabled.
- Explicit user approval of either a private ClassicSpeech runtime experiment or a separate NVDA-core experiment.
