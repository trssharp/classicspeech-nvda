"""Narrow Microsoft Edge UIA notification policy for ClassicSpeech.

Only exact activity IDs registered by the permanent ClassicSpeech Edge settings
panel are owned here. Other UIA notifications retain NVDA's native handling.
"""
from __future__ import annotations

import appModuleHandler
import ui

from globalPlugins._speech_core.settings import edge_notifications_config


class AppModule(appModuleHandler.AppModule):
    def event_UIA_notification(
        self,
        obj,
        nextHandler,
        notificationKind=None,
        notificationProcessing=None,
        displayString=None,
        activityId=None,
        **kwargs,
    ):
        """Apply the current per-activity Edge notification preference.

        Config is deliberately read per event so settings changes take effect
        immediately. Broken config access fails open to native NVDA handling.
        No download foreground heuristic is included: this module has no safe,
        tested UIA focus/tree predicate for such a policy.
        """
        if not isinstance(activityId, str) or activityId not in edge_notifications_config.ACTIVITY_IDS:
            nextHandler()
            return

        try:
            enabled_ids = edge_notifications_config.get_enabled_activity_ids()
            custom_messages = edge_notifications_config.get_custom_messages()
        except Exception:
            nextHandler()
            return

        if activityId not in enabled_ids:
            return

        try:
            custom_message = custom_messages.get(activityId)
        except Exception:
            nextHandler()
            return
        if isinstance(custom_message, str):
            custom_message = custom_message.strip()
            if custom_message:
                ui.message(custom_message)
                return
        nextHandler()
