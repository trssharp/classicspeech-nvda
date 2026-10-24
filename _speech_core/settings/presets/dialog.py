"""The existing presentation preset manager, in its own native dialog."""
import wx
from wx.lib import scrolledpanel
import gui

from ...localization import _
from ..dialog_transactions import SettingsDialogTransactionMixin
from .panel import PresentationPresetsPanel
from . import config_adapter
from .transaction import Transaction


class PresentationPresetsDialog(SettingsDialogTransactionMixin, wx.Dialog):
    shouldSuspendConfigProfileTriggers = True

    def __init__(self, parent):
        super().__init__(parent, title=_('ClassicSpeech Presentation Presets'),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER | wx.MAXIMIZE_BOX)
        self.SetName('ClassicSpeechPresentationPresetsDialog')
        self._destroying = False
        self._focusRequest = object()
        self._popupReleased = False
        self._committed = False
        self._initializeDialogTransaction()
        outer = wx.BoxSizer(wx.VERTICAL)
        self.panelHost = scrolledpanel.ScrolledPanel(self, style=wx.TAB_TRAVERSAL)
        content = wx.BoxSizer(wx.VERTICAL)
        self.presentationPresetsPanel = PresentationPresetsPanel(self.panelHost)
        # The native list consumes Enter unless its own char hook accepts it.
        # Share General/Web's OK path; selection must never imply Load.
        self.presentationPresetsPanel.presetList.Bind(wx.EVT_CHAR_HOOK, self.onCategoryCharHook)
        content.Add(self.presentationPresetsPanel, 1, wx.EXPAND)
        self.panelHost.SetSizer(content)
        self.panelHost.SetupScrolling(scroll_x=False)
        outer.Add(self.panelHost, 1, wx.ALL | wx.EXPAND, 8)
        row = wx.BoxSizer(wx.HORIZONTAL)
        row.AddStretchSpacer()
        self.okBtn = wx.Button(self, wx.ID_OK, label=_('OK'))
        self.cancelBtn = wx.Button(self, wx.ID_CANCEL, label=_('Cancel'))
        self.applyBtn = wx.Button(self, label=_('&Apply'))
        self.okBtn.SetDefault()
        for button in (self.okBtn, self.cancelBtn, self.applyBtn):
            row.Add(button, 0, wx.ALL, 8)
        outer.Add(row, 0, wx.EXPAND)
        self.SetSizer(outer)
        self.SetEscapeId(wx.ID_CANCEL)
        self.SetMinSize((700, 400))
        self.SetSize((850, 500))
        self.CentreOnParent()
        self.okBtn.Bind(wx.EVT_BUTTON, self.onOK)
        self.cancelBtn.Bind(wx.EVT_BUTTON, self.onCancel)
        self.applyBtn.Bind(wx.EVT_BUTTON, self.onApply)
        self.Bind(wx.EVT_CLOSE, self.onClose)
        self.Bind(wx.EVT_WINDOW_DESTROY, self._onWindowDestroyed)
        self.applyBtn.MoveAfterInTabOrder(self.cancelBtn)
        self._clearDirty()
        # Queue the Python owner, never a bound native control method.
        wx.CallAfter(self._focusPresetList, self._focusRequest)

    def _focusPresetList(self, request):
        if self._destroying or request is not self._focusRequest:
            return
        self._focusRequest = None
        if not self or self.IsBeingDeleted():
            return
        control = self.presentationPresetsPanel.presetList
        try:
            control.SetFocus()
        except RuntimeError as error:
            # A native deletion can still race the liveness check. Do not
            # suppress other focus errors, which indicate real defects.
            message = str(error)
            if not (message.startswith('wrapped C/C++ object of type ')
                    and message.endswith(' has been deleted')):
                raise

    def _beginDestroy(self):
        self._destroying = True
        self._focusRequest = None

    def Destroy(self):
        self._beginDestroy()
        return super().Destroy()

    def onCancel(self, event):
        self._beginDestroy()
        return super().onCancel(event)

    def onClose(self, event):
        self._beginDestroy()
        return super().onClose(event)

    def get_working_presentation(self):
        return config_adapter.capture()

    def load_working_presentation(self, snapshot):
        config_adapter.apply(snapshot)

    def _captureTransactionBaseline(self):
        self._transaction = Transaction()

    def _restoreTransactionBaseline(self):
        self._transaction.restore()

    def _saveTransaction(self):
        self.presentationPresetsPanel.library.serialize()
        self.presentationPresetsPanel.save_library()
        self.presentationPresetsPanel.refresh_status()

    def _markDirty(self):
        self.applyBtn.Show()
        self.applyBtn.Enable(True)
        self.Layout()

    def _clearDirty(self):
        self.applyBtn.Hide()
        self.applyBtn.Enable(False)
        self.Layout()

    def _onWindowDestroyed(self, event):
        if event.GetEventObject() is self:
            self._beginDestroy()
            self._restoreTransactionBaselineSafely()
            self._releaseTransactionPopup()
        event.Skip()

    def _releaseTransactionPopup(self):
        if not self._popupReleased:
            self._popupReleased = True
            gui.mainFrame.postPopup()
