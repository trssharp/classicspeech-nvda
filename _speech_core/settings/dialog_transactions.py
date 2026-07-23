"""Reusable Apply/OK/Cancel/Close transaction lifecycle for settings dialogs."""

import logHandler


log = logHandler.log


class SettingsDialogTransactionMixin:
	"""Own the common settings-dialog baseline transaction lifecycle.

	Subclasses provide four hooks:
	- ``_captureTransactionBaseline`` snapshots all state the dialog owns.
	- ``_saveTransaction`` writes the current controls/configuration.
	- ``_restoreTransactionBaseline`` restores the last successful baseline.
	- ``_releaseTransactionPopup`` releases the NVDA popup after close.
	"""

	def _initializeDialogTransaction(self):
		self._captureTransactionBaseline()

	def onApply(self, event):
		try:
			self._saveTransaction()
			# Rebase only after a fully successful save. A failed Apply must keep
			# the earlier rollback state for Cancel or window Close.
			self._captureTransactionBaseline()
			self._committed = True
			self._clearDirty()
			return True
		except Exception:
			log.exception("ClassicSpeech settings apply failed")
			return False

	def onOK(self, event):
		if self.onApply(event):
			self.Destroy()

	def onCancel(self, event):
		self._restoreTransactionBaselineSafely()
		self.Destroy()

	def onClose(self, event):
		try:
			self._restoreTransactionBaselineSafely()
		finally:
			try:
				event.Skip()
			finally:
				self._releaseTransactionPopup()

	def _restoreTransactionBaselineSafely(self):
		try:
			self._restoreTransactionBaseline()
		except Exception:
			log.exception("ClassicSpeech settings dialog state restoration failed")
