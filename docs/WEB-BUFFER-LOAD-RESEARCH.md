# Web Buffer Load Research — NVDA Master Verified

**Status:** historical source research. It does not authorize a ClassicSpeech virtual-buffer patch, buffer mutation, or structural-line insertion. The supported add-on API has no virtual-buffer write path; such work requires a separately approved NVDA-core design.

## Scope

This note records what NVDA master establishes about virtual-buffer loading and why Firefox/Gecko can feel noisier than Chromium-family browsers during navigation. It does not claim that every audible page-load message originates from one source; browser accessibility events, NVDA focus reporting, and virtual-buffer completion are separate event paths.

## Verified NVDA virtual-buffer lifecycle

NVDA master `source/virtualBuffers/__init__.py` implements this sequence:

1. `VirtualBuffer.prepare()` calls `loadBuffer()`.
2. `loadBuffer()` sets `isLoading = True`, starts a one-second delayed progress callback, and creates the buffer on a background thread.
3. If loading lasts at least one second, `_loadProgress()` calls `ui.message("Loading document...")`.
4. The background operation creates the native virtual buffer and queues `_loadBufferDone()` on NVDA's event queue.
5. `_loadBufferDone()` clears `isLoading`. An empty initial buffer remains pending for a later document-load-complete event.
6. If the focused object is still this tree interceptor, completion calls `event_treeInterceptor_gainFocus()`.
7. `event_documentLoadComplete()` handles the initial focus/reporting path when initial focus arrived too early for the buffer to report content.
8. A refresh after the first focused load emits NVDA's native `ui.message("Refreshed")`.

Consequences:

- Buffer construction, document-load-complete, focus reporting, title reporting, live-region speech, and browser state changes can arrive in different orders.
- An observed page announcement can therefore be title-only, title plus a focused element, first-line content, or another event emitted while the page is settling.
- A global speech flush during `isLoading` would risk dropping legitimate focus changes, dialogs, errors, live regions, and user-initiated commands.

## Verified Gecko versus Chromium Busy distinction

Firefox uses NVDA's Gecko IAccessible2 virtual buffer (`source/virtualBuffers/gecko_ia2.py`). Its Gecko buffer remains alive while `isLoading` is true. NVDA master does not add a Gecko-specific Busy-state gate before choosing that virtual-buffer class.

Chromium's document class has a specific `loadChromiumVBufOnBusyState` feature flag in `source/NVDAObjects/IAccessible/chromium.py`:

- By default, the flag is false.
- While a Chromium document is Busy, NVDA does **not** return the Chromium virtual-buffer class.
- If the feature flag is enabled, NVDA permits virtual-buffer loading while Busy.

This is a source-backed reason Firefox can expose a busier/earlier load lifecycle than Chrome, Edge, and other Chromium-based browsers. It does **not** by itself prove which Firefox accessibility event produces every audible "busy" announcement. That must be captured in a Firefox live log before ClassicSpeech suppresses anything.

## Confirmed native strings

- `Loading document...` is emitted by the virtual-buffer delayed progress callback after one second.
- `Refreshed` is emitted after a completed refresh if the buffer has previously gained focus.
- `busy` is NVDA's display string for `controlTypes.State.BUSY`.

## Historical recommendation and current boundary

The recommended additive lifecycle work was limited to optional page-loading and page-ready orientation. It must not be read as authorization for structural-buffer changes:

- **Announce page loading**: delayed, so fast navigations remain quiet.
- **Announce page ready**: only when the focused document's buffer is ready/complete.

Do not initially:

- flush global speech;
- block all speech while a buffer loads;
- replace page title or focus speech;
- suppress all text matching `busy`;
- count page elements or alter virtual-buffer content.

## Safe future investigation sequence

1. Add diagnostic-only Firefox/Chromium logging around document identity, buffer start, delayed progress, buffer ready, document-load-complete, focus, and nearby Busy-state events.
2. Compare Firefox, Chromium, and a non-Chromium browser with the same navigation pattern.
3. If a stable Firefox-only duplicated Busy source is proven, add an opt-in source/state-scoped coalescer for that specific lifecycle event.
4. Keep page title, focused controls, alerts, forms, live regions, and user commands outside that coalescer.

## Design conclusion

Optional page-ready orientation remains separate from virtual-buffer manipulation. It is additive and buffer-identity scoped, not a blanket speech suppression system; it does not insert lines, alter buffer semantics, or suppress native structural speech.
