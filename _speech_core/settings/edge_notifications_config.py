"""Registry-backed persistent settings for ordinary Microsoft Edge notifications."""
from __future__ import annotations

import copy
from collections import namedtuple

from .config_core import _ensure_classic_speech_section


EdgeNotificationActivity = namedtuple("EdgeNotificationActivity", "activity_id label enabled_by_default")

# This registry is the only supported Activity ID inventory. Its order controls
# both persistence normalization and the eventual checklist presentation.
EDGE_NOTIFICATION_ACTIVITIES = (
    EdgeNotificationActivity("PageLoading", "Announce loading of pages", False),
    EdgeNotificationActivity("RefreshingPage", "Announce page refresh", False),
    EdgeNotificationActivity("ClosingTab", "Announce closing of tab", False),
    EdgeNotificationActivity("OpeningNewTab", "Announce Opening of new tab", False),
    EdgeNotificationActivity("OpeningWindow", "Announce window opening", False),
    EdgeNotificationActivity("OpeningInPrivateWindow", "Announce opening of inprivate window", False),
    EdgeNotificationActivity("GoingBack", "Announce navigating back", False),
    EdgeNotificationActivity("GoingForward", "Announce navigating forward", False),
    EdgeNotificationActivity("CantGoBack", "Announce if there is no previous page to navigate", False),
    EdgeNotificationActivity("CantGoForward", "Announce if there is no next page to navigate", False),
    EdgeNotificationActivity("HubDownloadsNewDownload", "Announce starting file download", True),
    EdgeNotificationActivity("HubDownloadsCompleteState", "Announce download completion", True),
    EdgeNotificationActivity("HubDownloadsInProgressState", "Announce progress state of current download", False),
    EdgeNotificationActivity("HubDownloadsIndeterminateProgressState", "Announce indeterminate progress state of current download", False),
    EdgeNotificationActivity("ToolbarButtonRemoved", "Announce removing toolbar buttons", False),
    EdgeNotificationActivity("SearchMode", "Announce of search mode", False),
    EdgeNotificationActivity("SearchModeAvailable", "Announce availability of search mode", False),
    EdgeNotificationActivity("NotificationAppear", "Announce appearing of notifications", False),
    # The installed add-on's later duplicate definition makes this enabled.
    EdgeNotificationActivity("UpdateNotification", "Announce update notifications", True),
    EdgeNotificationActivity("PageZoom", "Announce zoom changes", True),
    EdgeNotificationActivity("Autofill option here", "Announce autofil suggestions", False),
    EdgeNotificationActivity("AutofillSuggestionFilled", "Announce filling of autofill suggestions", False),
    EdgeNotificationActivity("PopupClosed", "Announce Closing popups like hiding  suggestions of autofill", False),
    EdgeNotificationActivity("AutofillSuggestionHideButton", "Announce hiding  autofill suggestions", False),
    EdgeNotificationActivity("RemoveSuggestion", "Announce removing a suggestion", True),
    EdgeNotificationActivity("ContentSettingNotification", "Announce content setting notifications", True),
    EdgeNotificationActivity("ExcelAutofillSuggestionTriggered", "Announce triggerring of autofill suggestions", True),
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


def _get_edge_notification_data():
    section = _ensure_classic_speech_section()
    data = section.get(EDGE_NOTIFICATION_DATA_KEY)
    if not hasattr(data, "get"):
        data = {}
        section[EDGE_NOTIFICATION_DATA_KEY] = data
    return data


def get_enabled_activity_ids() -> tuple[str, ...]:
    data = _get_edge_notification_data()
    if ENABLED_ACTIVITY_IDS_KEY not in data:
        return DEFAULT_ENABLED_ACTIVITY_IDS
    return normalize_enabled_activity_ids(data.get(ENABLED_ACTIVITY_IDS_KEY))


def set_enabled_activity_ids(activity_ids: object) -> tuple[str, ...]:
    normalized = normalize_enabled_activity_ids(activity_ids, malformed_defaults=False)
    _get_edge_notification_data()[ENABLED_ACTIVITY_IDS_KEY] = list(normalized)
    return normalized


def get_custom_messages() -> dict[str, str]:
    return normalize_custom_messages(_get_edge_notification_data().get(CUSTOM_MESSAGES_KEY))


def set_custom_messages(messages: object) -> dict[str, str]:
    normalized = normalize_custom_messages(messages)
    _get_edge_notification_data()[CUSTOM_MESSAGES_KEY] = dict(normalized)
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
    return {
        ENABLED_ACTIVITY_IDS_KEY: list(get_enabled_activity_ids()),
        CUSTOM_MESSAGES_KEY: copy.deepcopy(get_custom_messages()),
    }


def restore_edge_notification_state(snapshot: object) -> None:
    """Restore a capture, treating malformed captures as safe defaults."""
    if not hasattr(snapshot, "get"):
        snapshot = {}
    set_enabled_activity_ids(snapshot.get(ENABLED_ACTIVITY_IDS_KEY, DEFAULT_ENABLED_ACTIVITY_IDS))
    set_custom_messages(snapshot.get(CUSTOM_MESSAGES_KEY, {}))
