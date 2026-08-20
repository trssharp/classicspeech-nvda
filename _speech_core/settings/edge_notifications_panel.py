"""Editable Microsoft Edge notification controls for the settings dialog."""
from __future__ import annotations
from ..localization import _


from .edge_notifications_config import (
    EDGE_NOTIFICATION_ACTIVITIES,
    normalize_custom_messages,
    normalize_enabled_activity_ids,
)
from .rename_list_panel import RenameListPanel


class EdgeNotificationsPanel(RenameListPanel):
    """Registry-backed checklist with separate enablement and custom wording."""

    _DESCRIPTION = (
        _("Space: announce or suppress. F2: set a custom announcement. "
        "Delete: restore the native Edge announcement. Shift+F10: menu.")
    )

    def __init__(self, parent, onChange=None):
        self._activityIds = [activity.activity_id for activity in EDGE_NOTIFICATION_ACTIVITIES]
        displayLabels = {
            activity.activity_id: activity.label
            for activity in EDGE_NOTIFICATION_ACTIVITIES
        }
        super().__init__(
            parent,
            title=_("Microsoft Edge notifications"),
            labels=self._activityIds,
            renames={},
            mutedLabels=[],
            onChange=onChange,
            displayLabels=displayLabels,
            helpText=self._DESCRIPTION,
            compactDisplay=True,
            renamePromptTitle=_("Custom notification message: {display}"),
            renamePromptMessage=(
                _("Enter a custom notification message for '{display}'. "
                "Leave blank to restore the native Edge announcement.")
            ),
            renameMenuLabel=_("Set custom message\tF2"),
            clearRenameMenuLabel=_("Restore native message\tDelete"),
            checkedActionCaption=_("Announce"),
            uncheckedActionCaption=_("Suppress"),
            customDisplaySuffix=_("custom message: {text}"),
        )

    def loadData(self, enabledActivityIds, customMessages):
        # Config getters expose normalized IDs as a tuple, while the persistence
        # normalizer intentionally treats only lists as stored config values.
        if isinstance(enabledActivityIds, tuple):
            enabledActivityIds = list(enabledActivityIds)
        enabledIds = normalize_enabled_activity_ids(enabledActivityIds)
        customMessages = normalize_custom_messages(customMessages)
        mutedIds = [activityId for activityId in self._activityIds if activityId not in enabledIds]
        super().loadData(customMessages, mutedIds)

    def getEnabledActivityIds(self):
        enabledIds = [
            activityId
            for activityId in self._activityIds
            if activityId not in self._workingMuted
        ]
        return normalize_enabled_activity_ids(enabledIds, malformed_defaults=False)

    def getCustomMessages(self):
        return normalize_custom_messages(self.getRenames())
