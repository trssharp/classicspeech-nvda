"""Shared settings dialog transaction lifecycle regression harness."""
from __future__ import annotations

import sys
import unittest
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
		from globalPlugins._speech_core.settings.web_settings_dialog import WebBrowseSettingsDialog

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


if __name__ == "__main__":
	unittest.main()
