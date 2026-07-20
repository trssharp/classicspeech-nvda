# history_viewer.py
"""Simple wx dialog for reviewing ClassicSpeech history."""

import wx

import api
import gui
import logHandler
import ui

log = logHandler.log

_HISTORY_DIALOG_ACTIVE = False
_HISTORY_LIST_HANDLE = None


def is_history_dialog_active():
    return _HISTORY_DIALOG_ACTIVE


def _role_matches(role, *needles):
    try:
        role_text = getattr(role, "displayString", None) or str(role)
    except Exception:
        role_text = ""
    role_text = role_text.lower().replace("_", " ")
    return any(needle in role_text for needle in needles)


def _sequence_text(sequence):
    parts = []
    for item in sequence or []:
        if isinstance(item, str):
            text = item.strip()
            if text:
                parts.append(text)
    return " ".join(parts).strip()


def is_history_list_focus(sequence=None):
    """Return True only for navigation on actual Speech History entries.

    History entries are already-final strings, so individual list items should
    speak natively. The list control itself should still pass through
    ClassicSpeech so verbosity/profile rules can apply to the list role.
    Other controls in the dialog, such as Copy/Clear/Close, should also use
    normal ClassicSpeech processing.
    """
    if not _HISTORY_DIALOG_ACTIVE or not _HISTORY_LIST_HANDLE:
        return False

    # NVDA may emit a standalone list-control announcement such as
    # ["list", CancellableSpeech] immediately before/after selected item
    # speech. Let that pass through ClassicSpeech so role renames and
    # verbosity settings still apply to the list control itself.
    spoken_text = _sequence_text(sequence).lower()
    if spoken_text in {"list", "list view"}:
        return False

    try:
        focus = api.getFocusObject()
    except Exception:
        return False

    try:
        focus_role = getattr(focus, "role", None)
    except Exception:
        focus_role = None

    # Let the list control itself be processed normally. Only flattened history
    # entries/list items bypass ClassicSpeech token classification.
    if _role_matches(focus_role, "list item", "listitem"):
        current = focus
        depth = 0
        while current is not None and depth < 6:
            try:
                if getattr(current, "windowHandle", None) == _HISTORY_LIST_HANDLE:
                    return True
            except Exception:
                pass
            try:
                current = getattr(current, "parent", None)
            except Exception:
                break
            depth += 1

    return False


class SpeechHistoryDialog(wx.Dialog):
    def __init__(self, parent, history):
        global _HISTORY_DIALOG_ACTIVE
        _HISTORY_DIALOG_ACTIVE = True
        super().__init__(parent, title="Speech History")
        self.history = history

        mainSizer = wx.BoxSizer(wx.VERTICAL)

        self.listBox = wx.ListBox(self, choices=self.history.items(), style=wx.LB_SINGLE)
        global _HISTORY_LIST_HANDLE
        try:
            _HISTORY_LIST_HANDLE = self.listBox.GetHandle()
        except Exception:
            _HISTORY_LIST_HANDLE = None
        mainSizer.Add(self.listBox, proportion=1, flag=wx.EXPAND | wx.ALL, border=10)

        buttonSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.copyButton = wx.Button(self, label="&Copy")
        self.clearButton = wx.Button(self, label="C&lear")
        self.closeButton = wx.Button(self, id=wx.ID_CLOSE, label="Close")

        buttonSizer.Add(self.copyButton, flag=wx.RIGHT, border=8)
        buttonSizer.Add(self.clearButton, flag=wx.RIGHT, border=8)
        buttonSizer.AddStretchSpacer(1)
        buttonSizer.Add(self.closeButton)
        mainSizer.Add(buttonSizer, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=10)

        self.SetSizer(mainSizer)
        self.SetMinSize((520, 360))
        self.Fit()

        self.copyButton.SetDefault()

        self.copyButton.Bind(wx.EVT_BUTTON, self.onCopy)
        self.clearButton.Bind(wx.EVT_BUTTON, self.onClear)
        self.closeButton.Bind(wx.EVT_BUTTON, self.onClose)
        self.Bind(wx.EVT_CLOSE, self.onClose)
        self.Bind(wx.EVT_CHAR_HOOK, self.onCharHook)

        self._refreshButtons()
        if self.listBox.GetCount():
            self.listBox.SetSelection(0)
            self.listBox.SetFocus()
        else:
            self.closeButton.SetFocus()

    def _refreshButtons(self):
        hasItems = self.listBox.GetCount() > 0
        self.copyButton.Enable(hasItems)
        self.clearButton.Enable(hasItems)

    def _selectedIndex(self):
        index = self.listBox.GetSelection()
        if index == wx.NOT_FOUND:
            return None
        return index

    def onCopy(self, event=None):
        index = self._selectedIndex()
        if index is None:
            ui.message("No history item selected")
            return
        self.history.copy_index(index)

    def onClear(self, event):
        self.history.clear()
        self.listBox.Clear()
        self._refreshButtons()
        ui.message("Speech history cleared")
        self.closeButton.SetFocus()

    def onCharHook(self, event):
        key = event.GetKeyCode()
        if key == wx.WXK_ESCAPE:
            self.Close()
            return
        if key in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self.onCopy()
            return
        event.Skip()

    def onClose(self, event):
        global _HISTORY_DIALOG_ACTIVE, _HISTORY_LIST_HANDLE
        _HISTORY_DIALOG_ACTIVE = False
        _HISTORY_LIST_HANDLE = None
        self.Destroy()


def show_history_dialog(history):
    gui.mainFrame.prePopup()
    dialog = SpeechHistoryDialog(gui.mainFrame, history)

    def _postPopup(evt):
        try:
            evt.Skip()
        finally:
            try:
                gui.mainFrame.postPopup()
            except Exception:
                log.debug("ClassicSpeech history dialog: postPopup failed", exc_info=True)

    dialog.Bind(wx.EVT_WINDOW_DESTROY, _postPopup)
    dialog.Show()
