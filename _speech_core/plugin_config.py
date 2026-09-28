"""ClassicSpeech plugin config spec and startup helpers."""

import config
import logHandler

from .nvda_settings_backup import classic_speech_settings_exist
from .update_channels import default_update_channel
from .settings.edge_notifications_config import DEFAULT_ENABLED_ACTIVITY_IDS

log = logHandler.log

_EDGE_NOTIFICATION_DEFAULT_IDS_SPEC = ", ".join(repr(activity_id) for activity_id in DEFAULT_ENABLED_ACTIVITY_IDS)

# Register the correct default before NVDA/ConfigObj can materialize it.
# Loading settings.ini afterwards still replaces it with an explicit choice.
DEFAULT_UPDATE_CHANNEL = default_update_channel()

_CLASSIC_SPEECH_SPEC = {
    "defaultProfile": "string(default='Beginner')",
    "announceDefaultButton": "boolean(default=False)",
    "preventAutomaticSpeechInterrupt": "boolean(default=False)",
    "automaticSpeechInterruptFallbackMs": "integer(default=1000)",
    # Speak ClassicSpeech's own messages first; only a key press interrupts them.
    "prioritizeMessages": "boolean(default=False)",
    "queryObjectSource": "string(default='focus')",
    "objectNavigationProcessing": "boolean(default=False)",
    "speechHookEnabled": "boolean(default=True)",
    "announceSpeechHookLoaded": "boolean(default=False)",
    "speechHookLoadedMessage": "string(default='ClassicSpeech hook loaded')",
    "debugLogging": "boolean(default=False)",
    "checkForUpdatesAutomatically": "boolean(default=True)",
    "updateChannel": f"string(default='{DEFAULT_UPDATE_CHANNEL}')",
    # Seconds since the epoch of the last successful update check.
    "lastUpdateCheck": "integer(default=0)",
    "announceMenuOpen": "boolean(default=True)",
    "announceMenuClose": "boolean(default=True)",
    "announceMenuBarFocus": "boolean(default=True)",
    "announceMenuBarLeave": "boolean(default=False)",
    "menuOpenMessage": "string(default='Entering menu')",
    "menuCloseMessage": "string(default='Leaving menu')",
    "menuBarFocusMessage": "string(default='Menu bar')",
    "menuBarLeaveMessage": "string(default='Leaving menu bar')",
    "hotkeyMode": "string(default='both')",
    "hotkeyFormat": "string(default='native')",
    "hotkeyTypes": "string(default='both')",
    "hotkeyDialogAccessKeyOnly": "boolean(default=False)",
    "positionMode": "string(default='each')",
    "readEditFieldContents": "boolean(default=True)",
    "textProcessingData": {
        "announceNewLinesDuringSayAll": "boolean(default=False)",
        "newLineMessage": "string(default='new line')",
        "splitMixedCaseWords": "boolean(default=False)",
        "suppressWordInternalDashes": "boolean(default=False)",
        "spellAlphanumericData": "string(default='off')",
        "listItemStateReporting": "string(default='notSelected')",
        "repeatedCharacterMode": "string(default='3')",
        "filterRepeatedCharacters": "boolean(default=False)",
        "repeatedCharacterLimit": "integer(default=3, min=1, max=20)",
    },
    "numberProcessingData": {
        "numberProcessingMode": "string(default='synthesizer')",
        "singleDigitsIfNumberContains": "string(default='synthesizer')",
        "phoneNumberProcessing": "string(default='native')",
        "friendlyTollFreePrefixes": "boolean(default=True)",
        "currencyProcessing": "string(default='native')",
        "ordinalProcessing": "string(default='native')",
        "numericDateProcessing": "string(default='native')",
        "numericDateFormat": "string(default='mdy')",
        "recognizeIsoDates": "boolean(default=True)",
        "useWindowsDateFormat": "boolean(default=False)",
    },
    "profileData": {
        "__many__": {
            "enabledTokens": {
                "name": "boolean(default=True)",
                "role": "boolean(default=True)",
                "state": "boolean(default=True)",
                "position": "boolean(default=True)",
                "description": "boolean(default=True)",
                "tooltip": "boolean(default=False)",
                "hotkey": "boolean(default=True)",
            },
        },
    },
    "profileBehaviorData": {
        "__many__": {
            "positionMode": "string(default='each')",
            "readEditFieldContents": "boolean(default=True)",
        },
    },
    "pageSummaryData": {
        "includedElementTypes": "string_list(default=list('heading', 'landmark', 'link', 'formField', 'button', 'table'))",
        "includeDocumentTitle": "boolean(default=False)",
        "automaticReportOnPageLoad": "boolean(default=False)",
        "pageLoadSummaryMode": "string(default='native')",
        "pageEntrySummaryDelaySeconds": "integer(default=2, min=0, max=5)",
        "notifyWhenPageReady": "boolean(default=False)",
        "pageReadyMessage": "string(default='Page ready')",
    },
    "headingContinuityData": {
        "enabled": "boolean(default=False)",
    },
    "modeIndicationData": {
        "browseModeMessage": "string(default='')",
        "focusModeMessage": "string(default='')",
    },
    "edgeNotificationData": {
        "enabledActivityIds": f"string_list(default=list({_EDGE_NOTIFICATION_DEFAULT_IDS_SPEC}))",
        "customMessages": {
            "__many__": "string(default='')",
        },
    },
    # Arbitrary synth setting types and nested baseline/override records are
    # serialized as JSON so ConfigObj validation cannot discard unknown keys.
    "voiceProfileData": "string(default='{}')",
    # Speech and Sound Schemes: sounds, voices and custom catalog entries,
    # serialized as JSON for the same reason as voiceProfileData.
    "schemeData": "string(default='{}')",
    # NVDA's start and exit sound option before ClassicSpeech took those sounds
    # over for a scheme's NVDA start sound, as JSON; empty otherwise.
    "nvdaStartExitSoundsState": "string(default='')",
    "keyLabelData": {
        "renames": {
            "__many__": "string(default='')",
        },
        "mutedLabels": "string_list(default=list())",
    },
    "shapeData": {
        "pauseMode": "string(default='global')",
        "globalPause": "integer(default=80)",
        "order": "string_list(default=list('name', 'role', 'value', 'state', 'position', 'description', 'hotkey'))",
        "renames": {
            "__many__": "string(default='')",
        },
        "mutedLabels": "string_list(default=list())",
        "pauses": {
            "name": "integer(default=-1)",
            "role": "integer(default=-1)",
            "value": "integer(default=-1)",
            "state": "integer(default=-1)",
            "position": "integer(default=-1)",
            "description": "integer(default=-1)",
            "hotkey": "integer(default=-1)",
        },
        "pauseAfterFinalToken": "boolean(default=True)",
        "pausePlacement": "string(default='before')",
    },
}


def _initClassicSpeechConfig():
    """
    Register the ClassicSpeech config section early, force it to live in the
    base config instead of riding NVDA config profiles, and load ClassicSpeech's
    settings into it from its own settings file (``settings_file``).

    Returns True when ClassicSpeech settings existed before this start.
    """
    try:
        config.conf.BASE_ONLY_SECTIONS.add("classicSpeech")
    except Exception:
        log.debug("ClassicSpeech: could not add section to BASE_ONLY_SECTIONS", exc_info=True)

    try:
        config.conf.spec["classicSpeech"] = _CLASSIC_SPEECH_SPEC
    except Exception:
        log.exception("ClassicSpeech: failed to register config spec")
        return False

    try:
        from .settings_file import load_into_nvda

        load_into_nvda()
    except Exception:
        log.exception("ClassicSpeech: failed to load its settings file")
    had_settings = classic_speech_settings_exist()

    # The NVDA config manager owns validation of its base ConfigObj. A late
    # add-on section is safe to register in ``config.conf.spec`` here, but
    # manually assigning its ConfigObj configspec and calling ``validate`` on
    # the already-materialized section is not: NVDA may expose schema leaves as
    # strings at this point. Normalize existing Boolean leaves before any
    # startup runtime reads them; otherwise a persisted ``"False"`` is truthy
    # until a settings panel live-applies the value.
    try:
        from .settings.config_core import _normalize_late_registered_boolean_values

        _normalize_late_registered_boolean_values(
            _getClassicSpeechSection(), _CLASSIC_SPEECH_SPEC
        )
    except Exception:
        log.debug("ClassicSpeech: could not normalize late Boolean config values", exc_info=True)
    return had_settings


def _getClassicSpeechSection():
    try:
        try:
            baseConf = config.conf.profiles[0]
        except Exception:
            baseConf = config.conf
        if "classicSpeech" not in baseConf:
            baseConf["classicSpeech"] = {}
        return baseConf["classicSpeech"]
    except Exception:
        log.exception("ClassicSpeech: failed reading config section")
        return {}
