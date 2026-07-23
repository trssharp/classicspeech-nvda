"""ClassicSpeech plugin config spec and startup helpers."""

import config
import logHandler

log = logHandler.log

_CLASSIC_SPEECH_SPEC = {
    "defaultProfile": "string(default='Beginner')",
    "announceDefaultButton": "boolean(default=False)",
    "preventAutomaticSpeechInterrupt": "boolean(default=False)",
    "automaticSpeechInterruptFallbackMs": "integer(default=1000)",
    "queryObjectSource": "string(default='focus')",
    "objectNavigationProcessing": "boolean(default=False)",
    "speechHookEnabled": "boolean(default=True)",
    "announceSpeechHookLoaded": "boolean(default=False)",
    "speechHookLoadedMessage": "string(default='ClassicSpeech hook loaded')",
    "debugLogging": "boolean(default=False)",
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
    "hotkeyDialogAccessKeyOnly": "boolean(default=False)",
    "positionMode": "string(default='each')",
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
        },
    },
    "pageSummaryData": {
        "includedElementTypes": "string_list(default=list('heading', 'landmark', 'link', 'formField', 'button', 'table'))",
        "includeDocumentTitle": "boolean(default=False)",
        "automaticReportOnPageLoad": "boolean(default=False)",
        "pageLoadSummaryMode": "string(default='native')",
    },
    # Arbitrary synth setting types and nested baseline/override records are
    # serialized as JSON so ConfigObj validation cannot discard unknown keys.
    "voiceProfileData": "string(default='{}')",
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
    },
}


def _initClassicSpeechConfig():
    """
    Register and validate the ClassicSpeech config section early, and force it to
    live in the base config instead of riding NVDA config profiles.
    """
    try:
        config.conf.BASE_ONLY_SECTIONS.add("classicSpeech")
    except Exception:
        log.debug("ClassicSpeech: could not add section to BASE_ONLY_SECTIONS", exc_info=True)

    try:
        config.conf.spec["classicSpeech"] = _CLASSIC_SPEECH_SPEC
    except Exception:
        log.exception("ClassicSpeech: failed to register config spec")
        return

    # The NVDA config manager owns validation of its base ConfigObj. A late
    # add-on section is safe to register in ``config.conf.spec`` here, but
    # manually assigning its ConfigObj configspec and calling ``validate`` on
    # the already-materialized section is not: NVDA may expose schema leaves as
    # strings at this point. Defaults are supplied by our getters until NVDA
    # reloads its base configuration normally.


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
