# ClassicSpeech Firefox Busy Runtime Patch Experiment

## Goal
Provide an opt-in, scratchpad-only experiment that suppresses only `State.BUSY` from one strict initial Firefox/Gecko Browse Mode focus presentation. It must not require a custom NVDA build or alter installed NVDA files.

## Safety contract
- Disabled by default.
- Patch only `NVDAObjects.IAccessible.mozilla.Document.reportFocus`.
- Match only the currently focused Gecko root document, in Browse Mode, loading and unready, with Busy present.
- Preserve the original focus method for every non-match and on every exception.
- Preserve real state/cache values. Never mutate `obj.states` or `_speakObjectPropertiesCache`.
- Remove only Busy from a copied presentation state set.
- Apply and restore patches by identity; restoration must not overwrite another add-on's later patch.
- Fail closed if required NVDA modules/signatures are absent or incompatible.
- Plugin unload/reload must restore all methods.

## Runtime mechanism
ClassicSpeech will temporarily wrap the Firefox `Document.reportFocus` method and, only while the strict predicate matches, set a context-local one-shot presentation filter. A wrapper around NVDA's property-to-speech formatter consumes that one shot, copies the `states` argument, removes `BUSY`, then calls the original formatter. The context is cleared in `finally` and any nonmatching call delegates unchanged.

## Gates
1. Harness tests for disabled/no-match/match, one-shot behavior, state copy/cache preservation, signature rejection, unload identity restoration, and reload safety.
2. Existing ClassicSpeech harness suite, compilation, and whitespace checks.
3. Independent source review.
4. Explicit approval before scratchpad deployment; deployment creates a backup and never replaces NVDA.
5. Live Firefox-on/off/reload and Edge-regression validation after user restarts NVDA.
