# _speech_core/cancelable.py

try:
    from speech.commands import CancellableSpeech
except ImportError:
    # fallback for older/different NVDA builds
    try:
        from speech import CancellableSpeech
    except ImportError:
        CancellableSpeech = None

import logHandler

log = logHandler.log


def unwrap_cancelable(sequence):
    """
    Recursively unwrap CancellableSpeech objects while preserving inner content.
    This removes NVDA's auto-interrupt behavior but keeps speech intact.
    """
    out = []

    for item in sequence:
        # Detect cancelable wrapper
        if CancellableSpeech and isinstance(item, CancellableSpeech):
            try:
                inner = getattr(item, "sequence", None)

                if inner:
                    log.debug(f"Unwrapping CancellableSpeech: {inner}")
                    # Recursively unwrap nested structures
                    out.extend(unwrap_cancelable(inner))
                else:
                    log.debug("CancellableSpeech had no inner sequence")

            except Exception as e:
                log.error(f"Error unwrapping CancellableSpeech: {e}")
                pass
        else:
            out.append(item)

    return out