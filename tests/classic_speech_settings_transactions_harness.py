"""Shared settings dialog transaction lifecycle regression harness."""
from __future__ import annotations

import sys
import unittest
from contextlib import ExitStack
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))
if str(ROOT / "tests") not in sys.path:
	sys.path.insert(0, str(ROOT / "tests"))

import classic_speech_nvda_master_harness as nvda_harness  # noqa: E402


class SettingsDialogTransactionTests(unittest.TestCase):
	def setUp(self):
		nvda_harness.ClassicSpeechNVDAConfigStartupTests().setUp()
		nvda_harness._import_classic_speech_like_nvda()
		from globalPlugins._speech_core.settings.dialog import ClassicSpeechDialog
		from globalPlugins._speech_core.settings.dialog_transactions import SettingsDialogTransactionMixin
		from globalPlugins._speech_core.settings.web.dialog import WebBrowseSettingsDialog

		self.dialog_types = (ClassicSpeechDialog, WebBrowseSettingsDialog)
		self.transaction_mixin = SettingsDialogTransactionMixin

	def tearDown(self):
		nvda_harness._reset_global_plugin_imports()

	def _make_dialog(self, dialog_type):
		dialog = object.__new__(dialog_type)
		dialog.state = "original"
		dialog._popupReleased = False
		dialog._committed = False
		dialog.clear_count = 0
		dialog.destroy_count = 0
		dialog.release_count = 0

		def capture():
			dialog.baseline = dialog.state

		def save():
			dialog.state = dialog.pending

		def restore():
			dialog.state = dialog.baseline

		dialog._captureTransactionBaseline = capture
		dialog._saveTransaction = save
		dialog._restoreTransactionBaseline = restore
		dialog._clearDirty = lambda: setattr(dialog, "clear_count", dialog.clear_count + 1)
		dialog.Destroy = lambda: setattr(dialog, "destroy_count", dialog.destroy_count + 1)
		dialog._releaseTransactionPopup = lambda: setattr(dialog, "release_count", dialog.release_count + 1)
		dialog._initializeDialogTransaction()
		return dialog

	def _make_bound_dialog(self, dialog_type):
		"""Run the concrete constructor; record per-control native-shaped binds.

		Panel content and storage are outside this event-routing fixture. Do not
		bind the new handler in the fixture: the real constructor must do it.
		"""
		import wx
		module = sys.modules[dialog_type.__module__]
		dialog = self._make_dialog(dialog_type)
		bindings = {}

		def bind(control, event_type, handler, *args, **kwargs):
			bindings.setdefault(id(control), {}).setdefault(event_type, []).append(handler)

		with ExitStack() as stack:
			for control_type in (wx.Dialog, wx.ListCtrl, wx.Button):
				stack.enter_context(patch.object(control_type, "Bind", bind, create=True))
			stack.enter_context(patch.object(wx, "WXK_RETURN", 13, create=True))
			stack.enter_context(patch.object(wx, "WXK_NUMPAD_ENTER", 370, create=True))
			# General's panels and Web's panel builders have separate config tests.
			for name, value in vars(module).items():
				if name.endswith("Panel") and isinstance(value, type):
					stack.enter_context(patch.object(module, name, wx.Panel))
			for name in ("_make_browse_mode_panel", "_make_web_reporting_panel",
				"_make_page_summary_panel", "_make_edge_notifications_panel"):
				if name in dialog_type.__dict__:
					stack.enter_context(patch.object(dialog_type, name, lambda *args: None))
			dialog_type.__init__(dialog, None)
		dialog.bindings = bindings
		return dialog

	def _dispatch_key(self, dialog, control, key, modifiers=0):
		import wx

		class KeyEvent:
			skips = 0
			def GetKeyCode(self): return key
			def GetModifiers(self): return modifiers
			def HasAnyModifiers(self): return bool(modifiers)
			def Skip(self): self.skips += 1

		event = KeyEvent()
		with patch.object(wx, "WXK_RETURN", 13, create=True), patch.object(
			wx, "WXK_NUMPAD_ENTER", 370, create=True,
		):
			for handler in dialog.bindings.get(id(control), {}).get(wx.EVT_CHAR_HOOK, []):
				handler(event)
		return event

	def test_category_enter_routes_once_through_ok_for_both_dialogs(self):
		import wx
		for dialog_type in self.dialog_types:
			for key in (13, 370):
				with self.subTest(dialog=dialog_type.__name__, key=key):
					dialog = self._make_bound_dialog(dialog_type)
					self.assertEqual(len(dialog.bindings[id(dialog.categoryList)].get(wx.EVT_CHAR_HOOK, [])), 1)
					dialog.pending = "accepted by Enter"
					with patch.object(dialog, "onOK", wraps=dialog.onOK) as ok:
						event = self._dispatch_key(dialog, dialog.categoryList, key)
						ok.assert_called_once_with(event)
					self.assertEqual(event.skips, 0)  # No second native/default activation.
					self.assertEqual(dialog.clear_count, 2)  # Construction and one Apply.
					self.assertEqual(dialog.destroy_count, 1)
					self.assertEqual(dialog.baseline, "accepted by Enter")
					dialog.onClose(self._close_event())
					self.assertEqual(dialog.state, "accepted by Enter")

	def test_category_other_keys_skip_and_other_controls_are_not_hooked(self):
		import wx
		for dialog_type in self.dialog_types:
			with self.subTest(dialog=dialog_type.__name__):
				dialog = self._make_bound_dialog(dialog_type)
				self.assertEqual(len(dialog.bindings[id(dialog.categoryList)].get(wx.EVT_CHAR_HOOK, [])), 1)
				# Space, navigation, Tab, Escape, letters, Ctrl+S, modified Enter.
				for key, modifiers in ((32, 0), (315, 0), (317, 0), (9, 0), (27, 0), (65, 0), (83, 2), (13, 2), (370, 4)):
					event = self._dispatch_key(dialog, dialog.categoryList, key, modifiers)
					self.assertEqual(event.skips, 1)
				self.assertEqual(dialog.state, "original")
				self.assertEqual(dialog.destroy_count, 0)
				self.assertEqual(dialog.clear_count, 1)
				for control in (dialog, dialog.okBtn, dialog.cancelBtn, dialog.applyBtn, dialog.panelHost, *dialog.dynamicPanels):
					self.assertNotIn(wx.EVT_CHAR_HOOK, dialog.bindings.get(id(control), {}))
				for control, handler in ((dialog.okBtn, dialog.onOK), (dialog.cancelBtn, dialog.onCancel), (dialog.applyBtn, dialog.onApply)):
					self.assertEqual(dialog.bindings[id(control)][wx.EVT_BUTTON], [handler])
				self.assertEqual(dialog.bindings[id(dialog.categoryList)][wx.EVT_LIST_ITEM_FOCUSED], [dialog.onCategoryChanged])
				self.assertEqual(len(dialog.bindings[id(dialog.categoryList)]), 2)

	def test_category_enter_save_failure_stays_open_and_keeps_applied_baseline(self):
		for dialog_type in self.dialog_types:
			for key in (13, 370):
				for close_with in ("onCancel", "onClose"):
					with self.subTest(dialog=dialog_type.__name__, key=key, close=close_with):
						dialog = self._make_bound_dialog(dialog_type)
						dialog.pending = "applied"
						self.assertTrue(dialog.onApply(None))
						dialog.state = "later live edit"
						dialog._saveTransaction = lambda: (_ for _ in ()).throw(RuntimeError("save failed"))
						with patch.object(dialog, "onOK", wraps=dialog.onOK) as ok:
							event = self._dispatch_key(dialog, dialog.categoryList, key)
							ok.assert_called_once_with(event)
						self.assertEqual(event.skips, 0)
						self.assertEqual(dialog.destroy_count, 0)
						self.assertEqual(dialog.baseline, "applied")
						getattr(dialog, close_with)(self._close_event())
						self.assertEqual(dialog.state, "applied")

	@staticmethod
	def _close_event():
		return type("CloseEvent", (), {
			"skipped": False,
			"Skip": lambda self: setattr(self, "skipped", True),
		})()

	def test_general_and_web_use_the_same_transaction_handlers(self):
		for dialog_type in self.dialog_types:
			with self.subTest(dialog=dialog_type.__name__):
				self.assertTrue(issubclass(dialog_type, self.transaction_mixin))
				for handler in ("onApply", "onOK", "onCancel", "onClose"):
					self.assertIs(getattr(dialog_type, handler), getattr(self.transaction_mixin, handler))

	def test_general_and_web_share_apply_ok_cancel_and_close_lifecycle(self):
		for dialog_type in self.dialog_types:
			with self.subTest(dialog=dialog_type.__name__):
				dialog = self._make_dialog(dialog_type)

				# OK applies and rebases. Its ensuing EVT_CLOSE restores that accepted
				# baseline, preserves Skip, and releases the popup.
				dialog.pending = "accepted"
				dialog.onOK(None)
				self.assertEqual(dialog.state, "accepted")
				self.assertEqual(dialog.destroy_count, 1)
				accepted_close = self._close_event()
				dialog.onClose(accepted_close)
				self.assertEqual(dialog.state, "accepted")
				self.assertTrue(accepted_close.skipped)
				self.assertEqual(dialog.release_count, 1)

				# A failed Apply does not replace the last successful baseline or close.
				dialog.state = "live failed apply"
				dialog.pending = "ignored"
				dialog._saveTransaction = lambda: (_ for _ in ()).throw(RuntimeError("apply failed"))
				self.assertFalse(dialog.onApply(None))
				self.assertEqual(dialog.destroy_count, 1)
				failed_close = self._close_event()
				dialog.onClose(failed_close)
				self.assertEqual(dialog.state, "accepted")
				self.assertTrue(failed_close.skipped)

				# Apply rebases; a later live change is rolled back by Cancel, and the
				# Destroy-generated Close safely repeats the same restoration.
				dialog._saveTransaction = lambda: setattr(dialog, "state", dialog.pending)
				dialog.pending = "applied"
				self.assertTrue(dialog.onApply(None))
				dialog.state = "later live edit"
				dialog.onCancel(None)
				self.assertEqual(dialog.state, "applied")
				self.assertEqual(dialog.destroy_count, 2)
				cancel_close = self._close_event()
				dialog.onClose(cancel_close)
				self.assertEqual(dialog.state, "applied")
				self.assertTrue(cancel_close.skipped)
				self.assertEqual(dialog.release_count, 3)
	def test_close_preserves_skip_and_releases_popup_when_restore_fails(self):
		for dialog_type in self.dialog_types:
			with self.subTest(dialog=dialog_type.__name__):
				dialog = self._make_dialog(dialog_type)
				dialog._restoreTransactionBaseline = lambda: (_ for _ in ()).throw(RuntimeError("restore failed"))
				event = self._close_event()
				dialog.onClose(event)
				self.assertTrue(event.skipped)
				self.assertEqual(dialog.release_count, 1)


class VoiceProfileListEnterTests(unittest.TestCase):
	setUp = SettingsDialogTransactionTests.setUp
	tearDown = SettingsDialogTransactionTests.tearDown
	_dispatch_key = SettingsDialogTransactionTests._dispatch_key
	_close_event = staticmethod(SettingsDialogTransactionTests._close_event)

	def _make_bound_dialog(self):
		import wx
		from unittest.mock import Mock
		from globalPlugins._speech_core.settings import voice_profiles_dialog as module

		bindings = {}
		def bind(control, event_type, handler, *args, **kwargs):
			bindings.setdefault(id(control), {}).setdefault(event_type, []).append(handler)

		with ExitStack() as stack:
			for control_type in (wx.Dialog, wx.ListCtrl, wx.Button, wx.Panel, wx.TextCtrl):
				stack.enter_context(patch.object(control_type, "Bind", bind, create=True))
			stack.enter_context(patch.object(wx, "ALIGN_BOTTOM", 0, create=True))
			store = stack.enter_context(patch.object(module, "VoiceProfileStore")).return_value
			store.rows = []
			stack.enter_context(patch.object(module.schemeStore, "SchemeStore"))
			# Keep real construction and list/button bindings, not dynamic editors.
			stack.enter_context(patch.object(module.VoiceProfilesDialog, "_select_profile"))
			dialog = module.VoiceProfilesDialog(None, driver=Mock())
		dialog.bindings = bindings
		dialog.Destroy = Mock()
		dialog._clear_editor = Mock()
		return dialog

	def test_profile_list_enter_invokes_existing_ok_once(self):
		import wx
		for key in (13, 370):
			with self.subTest(key=key):
				dialog = self._make_bound_dialog()
				self.assertEqual(len(dialog.bindings[id(dialog.profileList)].get(wx.EVT_CHAR_HOOK, [])), 1)
				with patch.object(dialog, "onOK", wraps=dialog.onOK) as ok:
					event = self._dispatch_key(dialog, dialog.profileList, key)
					ok.assert_called_once_with(event)
				self.assertEqual(event.skips, 0)
				for store in (dialog.store, dialog.schemeStore):
					store.apply.assert_called_once_with()
					store.mark_applied.assert_called_once_with()
				dialog._clear_editor.assert_called_once_with()
				dialog.Destroy.assert_called_once_with()

	def test_profile_list_save_failures_preserve_existing_transaction_order(self):
		for key in (13, 370):
			for failure in ("store", "schemeStore"):
				for close in ("onCancel", "onClose"):
					with self.subTest(key=key, failure=failure, close=close):
						dialog = self._make_bound_dialog()
						getattr(dialog, failure).apply.side_effect = RuntimeError("save failed")
						with patch.object(dialog, "onOK", wraps=dialog.onOK) as ok:
							event = self._dispatch_key(dialog, dialog.profileList, key)
							ok.assert_called_once_with(event)
						self.assertEqual(event.skips, 0)
						dialog.Destroy.assert_not_called()
						dialog._clear_editor.assert_not_called()
						getattr(dialog, failure).mark_applied.assert_not_called()
						# Existing Voice Profiles commits voice before scheme saving.
						self.assertEqual(dialog.store.mark_applied.call_count, int(failure == "schemeStore"))
						getattr(dialog, close)(self._close_event())
						dialog.store.cancel.assert_called_once_with()
						dialog.schemeStore.cancel.assert_called_once_with()

	def test_profile_list_other_keys_and_controls_keep_native_routes(self):
		import wx
		dialog = self._make_bound_dialog()
		for key, modifiers in [(key, 0) for key in (32, 314, 315, 316, 317, 9, 27, 65)] + [
			(key, modifier) for key in (13, 370) for modifier in (1, 2, 4, 8)
		] + [(83, 2)]:
			event = self._dispatch_key(dialog, dialog.profileList, key, modifiers)
			self.assertEqual(event.skips, 1)
		dialog.store.apply.assert_not_called()
		dialog.schemeStore.apply.assert_not_called()
		dialog.Destroy.assert_not_called()
		self.assertEqual(dialog.bindings[id(dialog.profileList)][wx.EVT_LIST_ITEM_FOCUSED], [dialog.onProfileChanged])
		self.assertEqual(len(dialog.bindings[id(dialog.profileList)]), 2)
		for control in (dialog, dialog.editorPanel, dialog.previewText, dialog.okBtn, dialog.cancelBtn,
			dialog.previewBtn, dialog.applyBtn, dialog.resetBtn, dialog.exportBtn, dialog.importBtn):
			self.assertNotIn(wx.EVT_CHAR_HOOK, dialog.bindings.get(id(control), {}))
		for control, handler in ((dialog.okBtn, dialog.onOK), (dialog.cancelBtn, dialog.onCancel),
			(dialog.previewBtn, dialog.onPreview), (dialog.applyBtn, dialog.onApply)):
			self.assertEqual(dialog.bindings[id(control)][wx.EVT_BUTTON], [handler])


if __name__ == "__main__":
	unittest.main()
