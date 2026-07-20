"""Small, targeted speech sequence coalescer for split container/item focus speech.

This intentionally does not manage keyboard interruption or general speech
queueing.  It only delays obvious container-only fragments briefly so a following
item fragment can be normalized into one predictable focus sequence.
"""

import re

import api
import core
import controlTypes
import logHandler
import speech

log = logHandler.log

MERGE_DELAY_MS = 60

_CONTAINER_ROLE_TEXT = {
    "list": "list",
    "list view": "list",
    "listview": "list",
    "tree": "tree",
    "tree view": "tree",
    "treeview": "tree",
}

_POSITION_RE = re.compile(r"^\s*\d+\s+of\s+\d+\s*$", re.I)
_STATE_TEXT = {
    "selected",
    "not selected",
    "checked",
    "not checked",
    "collapsed",
    "expanded",
}
_CHILD_ROLE_TEXT = {
    "list": "list item",
    "tree": "tree view item",
}


def _text_items(sequence):
    return [str(item).strip() for item in sequence if isinstance(item, str) and str(item).strip()]


def _norm(text):
    return " ".join(str(text or "").strip().lower().replace("_", " ").split())


class SequenceMerger:
    def __init__(self, owner=None, delay_ms=MERGE_DELAY_MS):
        self.owner = owner
        self.delay_ms = delay_ms
        self._pending = None
        self._pending_kind = None
        self._timer = None
        self.in_flush = False

    def terminate(self):
        self._cancel_timer()
        self._pending = None
        self._pending_kind = None

    def _cancel_timer(self):
        timer = self._timer
        self._timer = None
        if timer is not None:
            try:
                timer.Stop()
            except Exception:
                pass

    def _arm_timer(self):
        self._cancel_timer()
        try:
            self._timer = core.callLater(self.delay_ms, self._flush_pending)
        except Exception:
            log.debug("ClassicSpeech: sequence merge timer failed; flushing immediately", exc_info=True)
            self._flush_pending()

    def _focus_is_child_for(self, container_kind):
        try:
            role = getattr(api.getFocusObject(), "role", None)
            if container_kind == "list":
                return role == controlTypes.Role.LISTITEM
            if container_kind == "tree":
                return role == controlTypes.Role.TREEVIEWITEM
        except Exception:
            return False
        return False

    def _container_kind(self, sequence):
        texts = _text_items(sequence)
        if not texts or len(texts) > 3:
            return None
        if any(_POSITION_RE.fullmatch(text) for text in texts):
            return None

        normalized = [_norm(text) for text in texts]
        for text in normalized:
            kind = _CONTAINER_ROLE_TEXT.get(text)
            if kind:
                # Hold only structural-looking fragments.  A standalone list/tree
                # role or a short label + role is the pattern NVDA emits before
                # some real item announcements.
                return kind
        return None

    def _is_mergeable_item(self, sequence, container_kind):
        texts = _text_items(sequence)
        if not texts:
            return False
        normalized = [_norm(text) for text in texts]
        if any(text in _CONTAINER_ROLE_TEXT for text in normalized):
            return False
        if any(_POSITION_RE.fullmatch(text) for text in texts):
            return True
        return self._focus_is_child_for(container_kind)

    def _normalize_child_sequence(self, child_sequence, container_kind):
        texts = _text_items(child_sequence)
        if not texts:
            return list(child_sequence)

        names = []
        states = []
        positions = []
        role_text = _CHILD_ROLE_TEXT.get(container_kind, "list item")
        already_has_child_role = False

        for text in texts:
            n = _norm(text).rstrip(":")
            if _POSITION_RE.fullmatch(text):
                positions.append(text)
            elif n in {"list item", "tree view item", "treeview item"}:
                already_has_child_role = True
            elif n in _STATE_TEXT:
                states.append(text)
            else:
                names.append(text)

        if not names:
            return list(child_sequence)

        out = []
        out.extend(names)
        if not already_has_child_role:
            out.append(role_text)
        out.extend(states)
        out.extend(positions)
        return out

    def _flush_pending(self):
        self._cancel_timer()
        pending = self._pending
        self._pending = None
        self._pending_kind = None
        if not pending:
            return

        try:
            self.in_flush = True
            speech.speak(list(pending))
        except Exception:
            log.debug("ClassicSpeech: failed flushing pending merged speech", exc_info=True)
        finally:
            self.in_flush = False

    def handle(self, speech_sequence):
        """Return a sequence to continue processing, or None if consumed."""
        if self.in_flush:
            return speech_sequence

        sequence = list(speech_sequence)

        if self._pending is not None:
            pending = self._pending
            pending_kind = self._pending_kind
            self._pending = None
            self._pending_kind = None
            self._cancel_timer()

            if self._is_mergeable_item(sequence, pending_kind):
                merged = self._normalize_child_sequence(sequence, pending_kind)
                log.debug(
                    "ClassicSpeech: merged split %s container speech into child item sequence: %r -> %r",
                    pending_kind,
                    pending,
                    merged,
                )
                return merged

            # The next sequence was unrelated, so release the container first and
            # allow this sequence to continue normally.
            try:
                self.in_flush = True
                speech.speak(list(pending))
            except Exception:
                log.debug("ClassicSpeech: failed releasing unmerged container speech", exc_info=True)
            finally:
                self.in_flush = False

        kind = self._container_kind(sequence)
        if kind:
            self._pending = sequence
            self._pending_kind = kind
            self._arm_timer()
            log.debug("ClassicSpeech: holding split %s container speech briefly: %r", kind, sequence)
            return None

        return speech_sequence
