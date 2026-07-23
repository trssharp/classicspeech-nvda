"""Registry-backed persistent settings for ordinary Microsoft Edge notifications."""
from __future__ import annotations

import copy
from collections import namedtuple

import config

from .config_core import _ensure_classic_speech_section


EdgeNotificationActivity = namedtuple("EdgeNotificationActivity", "activity_id label enabled_by_default")

# This registry is the only supported Activity ID inventory. Its order controls
# both persistence normalization and the eventual checklist presentation.
EDGE_NOTIFICATION_ACTIVITIES = (
    EdgeNotificationActivity("PageLoading", "Page loading", False),
    EdgeNotificationActivity("RefreshingPage", "Page refresh", False),
    EdgeNotificationActivity("ClosingTab", "Close tab", False),
    EdgeNotificationActivity("OpeningNewTab", "New tab", False),
    EdgeNotificationActivity("OpeningWindow", "Open window", False),
    EdgeNotificationActivity("OpeningInPrivateWindow", "Open InPrivate window", False),
    EdgeNotificationActivity("GoingBack", "Back", False),
    EdgeNotificationActivity("GoingForward", "Forward", False),
    EdgeNotificationActivity("CantGoBack", "No previous page", False),
    EdgeNotificationActivity("CantGoForward", "No next page", False),
    EdgeNotificationActivity("HubDownloadsNewDownload", "Start download", True),
    EdgeNotificationActivity("HubDownloadsCompleteState", "Download completed", True),
    EdgeNotificationActivity("HubDownloadsInProgressState", "Download progress", False),
    EdgeNotificationActivity("HubDownloadsIndeterminateProgressState", "Download progress unavailable", False),
    EdgeNotificationActivity("ToolbarButtonRemoved", "Toolbar button removed", False),
    EdgeNotificationActivity("SearchMode", "Search mode", False),
    EdgeNotificationActivity("SearchModeAvailable", "Search mode available", False),
    EdgeNotificationActivity("NotificationAppear", "General browser notification", False),
    # The installed add-on's later duplicate definition makes this enabled.
    EdgeNotificationActivity("UpdateNotification", "Edge update", True),
    EdgeNotificationActivity("PageZoom", "Zoom changes", True),
    EdgeNotificationActivity("Autofill option here", "Autofill option", False),
    EdgeNotificationActivity("AutofillSuggestionFilled", "Autofill filled", False),
    EdgeNotificationActivity("PopupClosed", "Autofill popup closed", False),
    EdgeNotificationActivity("AutofillSuggestionHideButton", "Hide autofill suggestion", False),
    EdgeNotificationActivity("RemoveSuggestion", "Remove suggestion", True),
    EdgeNotificationActivity("ContentSettingNotification", "Site permission or content setting", True),
    EdgeNotificationActivity("ExcelAutofillSuggestionTriggered", "Excel autofill suggestion", True),
)

EDGE_NOTIFICATION_DATA_KEY = "edgeNotificationData"
ENABLED_ACTIVITY_IDS_KEY = "enabledActivityIds"
CUSTOM_MESSAGES_KEY = "customMessages"

ACTIVITY_IDS = tuple(activity.activity_id for activity in EDGE_NOTIFICATION_ACTIVITIES)
_ACTIVITY_ID_SET = frozenset(ACTIVITY_IDS)
DEFAULT_ENABLED_ACTIVITY_IDS = tuple(
    activity.activity_id for activity in EDGE_NOTIFICATION_ACTIVITIES if activity.enabled_by_default
)


def normalize_enabled_activity_ids(value: object, *, malformed_defaults: bool = True) -> tuple[str, ...]:
    """Return valid unique IDs in registry order.

    A persisted empty list is meaningful. Missing or malformed persisted data
    instead resolves to the installed add-on's effective defaults.
    """
    if not isinstance(value, list):
        return DEFAULT_ENABLED_ACTIVITY_IDS if malformed_defaults else ()
    try:
        selected = {item for item in value if isinstance(item, str) and item in _ACTIVITY_ID_SET}
    except Exception:
        return DEFAULT_ENABLED_ACTIVITY_IDS if malformed_defaults else ()
    return tuple(activity_id for activity_id in ACTIVITY_IDS if activity_id in selected)


def normalize_custom_messages(value: object) -> dict[str, str]:
    """Keep nonblank custom messages for recognized IDs, in registry order."""
    if not hasattr(value, "items"):
        return {}
    try:
        raw_messages = dict(value.items())
    except Exception:
        return {}
    normalized = {}
    for activity_id in ACTIVITY_IDS:
        message = raw_messages.get(activity_id)
        if isinstance(message, str):
            message = message.strip()
            if message:
                normalized[activity_id] = message
    return normalized


def _get_persisted_edge_notification_data() -> tuple[bool, object]:
    """Read persisted Edge data without creating ClassicSpeech config sections."""
    try:
        base_conf = config.conf.profiles[0]
    except Exception:
        base_conf = config.conf
    try:
        if "classicSpeech" not in base_conf:
            return False, None
        section = base_conf.get("classicSpeech")
        if not hasattr(section, "get") or EDGE_NOTIFICATION_DATA_KEY not in section:
            return False, None
        return True, section.get(EDGE_NOTIFICATION_DATA_KEY)
    except Exception:
        return False, None


def _get_edge_notification_data():
    """Return persisted mapping data, if any, without materializing defaults."""
    _exists, data = _get_persisted_edge_notification_data()
    return data if hasattr(data, "get") else None


def _ensure_edge_notification_data():
    """Return writable Edge data, creating config only for a setter."""
    section = _ensure_classic_speech_section()
    data = section.get(EDGE_NOTIFICATION_DATA_KEY)
    if not hasattr(data, "get"):
        data = {}
        section[EDGE_NOTIFICATION_DATA_KEY] = data
    return data


def get_enabled_activity_ids() -> tuple[str, ...]:
    data = _get_edge_notification_data()
    if data is None or ENABLED_ACTIVITY_IDS_KEY not in data:
        return DEFAULT_ENABLED_ACTIVITY_IDS
    return normalize_enabled_activity_ids(data.get(ENABLED_ACTIVITY_IDS_KEY))


def set_enabled_activity_ids(activity_ids: object) -> tuple[str, ...]:
    normalized = normalize_enabled_activity_ids(activity_ids, malformed_defaults=False)
    _ensure_edge_notification_data()[ENABLED_ACTIVITY_IDS_KEY] = list(normalized)
    return normalized


def get_custom_messages() -> dict[str, str]:
    data = _get_edge_notification_data()
    return normalize_custom_messages(data.get(CUSTOM_MESSAGES_KEY) if data is not None else None)


def set_custom_messages(messages: object) -> dict[str, str]:
    normalized = normalize_custom_messages(messages)
    _ensure_edge_notification_data()[CUSTOM_MESSAGES_KEY] = dict(normalized)
    return normalized


def set_custom_message(activity_id: object, message: object) -> str:
    """Set or clear one recognized custom message without changing enabled IDs."""
    if not isinstance(activity_id, str) or activity_id not in _ACTIVITY_ID_SET:
        return ""
    messages = get_custom_messages()
    normalized = message.strip() if isinstance(message, str) else ""
    if normalized:
        messages[activity_id] = normalized
    else:
        messages.pop(activity_id, None)
    set_custom_messages(messages)
    return normalized


def capture_edge_notification_state() -> dict[str, object]:
    """Capture plain, independent state suitable for settings-dialog Cancel."""
    has_data, persisted_data = _get_persisted_edge_notification_data()
    return {
        ENABLED_ACTIVITY_IDS_KEY: list(get_enabled_activity_ids()),
        CUSTOM_MESSAGES_KEY: copy.deepcopy(get_custom_messages()),
        "hasEdgeNotificationData": has_data,
        "edgeNotificationData": copy.deepcopy(persisted_data),
    }


def restore_edge_notification_state(snapshot: object) -> None:
    """Restore a capture, treating malformed captures as safe defaults."""
    if not hasattr(snapshot, "get"):
        snapshot = {}
    has_data = snapshot.get("hasEdgeNotificationData")
    if isinstance(has_data, bool):
        if has_data:
            _ensure_classic_speech_section()[EDGE_NOTIFICATION_DATA_KEY] = copy.deepcopy(
                snapshot.get("edgeNotificationData")
            )
        else:
            try:
                base_conf = config.conf.profiles[0]
            except Exception:
                base_conf = config.conf
            try:
                section = base_conf.get("classicSpeech")
                if hasattr(section, "__delitem__") and EDGE_NOTIFICATION_DATA_KEY in section:
                    del section[EDGE_NOTIFICATION_DATA_KEY]
            except Exception:
                pass
        return
    enabled_ids = normalize_enabled_activity_ids(snapshot.get(ENABLED_ACTIVITY_IDS_KEY))
    set_enabled_activity_ids(list(enabled_ids))
    set_custom_messages(snapshot.get(CUSTOM_MESSAGES_KEY, {}))
