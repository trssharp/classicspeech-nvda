"""Native keyboard-accessible preset library; edits are staged until Apply/OK."""
import wx
from gui import nvdaControls

from ...localization import _
from ..accessibility import _set_panel_description
from ..config_core import _ensure_classic_speech_section
from .model import Library, DEFAULT_ID, DEFAULT_NAME

CONFIG_KEY = 'presentationPresets'


class PresentationPresetsPanel(wx.Panel):
    def __init__(self, parent):
        super().__init__(parent)
        self.dialog = wx.GetTopLevelParent(self)
        from .transaction import base
        self.library = Library(base().get('classicSpeech', {}).get(CONFIG_KEY, ''),
                               self.dialog.get_working_presentation())
        self.libraryChanged = False
        description = _(
            'Save tokens, timing, all three verbosity profiles, menus, hotkeys, key labels, '
            'Misc title-window-state and default-button announcements, and Browse/Focus Mode indication together. '
            'Edit values in General Settings and Web / Browse Mode Settings. Selecting a preset does not load it. '
            'Older presets leave missing categories unchanged. Voices, schemes, interruption '
            'controls, Advanced and other native NVDA preferences are not included.'
        )
        _set_panel_description(self, _('Presentation Presets'), description)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(wx.StaticText(self, label=description), 0, wx.ALL | wx.EXPAND, 8)
        sizer.Add(wx.StaticText(self, label=_('&Presentation presets:')), 0, wx.ALL, 8)
        self.presetList = nvdaControls.AutoWidthColumnListCtrl(
            self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.LC_NO_HEADER)
        self.presetList.SetName(_('Presentation presets'))
        self.presetList.InsertColumn(0, _('Preset'))
        sizer.Add(self.presetList, 1, wx.ALL | wx.EXPAND, 8)
        row = wx.BoxSizer(wx.HORIZONTAL)
        for attr, label, handler in (
            ('loadBtn', _('&Load'), self.onLoad),
            ('saveAsBtn', _('Save &as...'), self.onSaveAs),
            ('updateBtn', _('&Update'), self.onUpdate),
            ('renameBtn', _('&Rename...'), self.onRename),
            ('deleteBtn', _('&Delete'), self.onDelete),
        ):
            button = wx.Button(self, label=label)
            setattr(self, attr, button)
            button.Bind(wx.EVT_BUTTON, handler)
            row.Add(button, 0, wx.ALL, 4)
        sizer.Add(row, 0, wx.ALL, 4)
        self.status = wx.StaticText(self, label='')
        sizer.Add(self.status, 0, wx.ALL | wx.EXPAND, 8)
        self.SetSizer(sizer)
        # No activation/Enter-to-load binding: arrows and list focus only select.
        self.presetList.Bind(wx.EVT_LIST_ITEM_FOCUSED, self.onSelection)
        self.refresh_list(self.library.loaded or DEFAULT_ID)

    def selected(self):
        index = self.presetList.GetFirstSelected()
        return self.keys[index] if 0 <= index < len(self.keys) else None

    def refresh_list(self, selected=None):
        self.keys = [DEFAULT_ID] + sorted(self.library.records,
                                        key=lambda k: self.library.records[k]['name'].casefold())
        self.presetList.DeleteAllItems()
        for key in self.keys:
            self.presetList.Append((_(DEFAULT_NAME) if key == DEFAULT_ID else self.library.records[key]['name'],))
        index = self.keys.index(selected) if selected in self.keys else 0
        self.presetList.Select(index)
        self.presetList.Focus(index)
        self.refresh_status()

    def refresh_status(self):
        key = self.selected()
        editable = key is not None and key != DEFAULT_ID and not self.library.read_only
        self.saveAsBtn.Enable(not self.library.read_only)
        self.loadBtn.Enable(key is not None)
        for button in (self.updateBtn, self.renameBtn, self.deleteBtn):
            button.Enable(editable)
        loaded = self.library.loaded
        name = (_(DEFAULT_NAME) if loaded == DEFAULT_ID else
                self.library.records[loaded]['name'] if loaded in self.library.records else _('Custom settings'))
        modified = self.library.modified(self.dialog.get_working_presentation())
        text = _('{name} — modified').format(name=name) if modified else name
        if self.library.read_only:
            text += _('. Unsupported preset library version: read-only; data kept unchanged. '
                      'Use a compatible ClassicSpeech version to edit it, or explicitly replace the library.')
        elif self.library.invalid:
            text += _('. Invalid preset data ignored; current settings kept.')
        self.status.SetLabel(text)
        self.Layout()

    def onSelection(self, event):
        event.Skip()
        self.refresh_status()

    def changed(self):
        self.libraryChanged = True
        self.dialog._markDirty()
        self.refresh_status()

    def confirm(self, message):
        return wx.MessageBox(message, _('Presentation Presets'),
                             wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION, self) == wx.YES

    def onLoad(self, event=None):
        from ...message_priority import speak_message
        from .transaction import Transaction
        import logHandler

        key = self.selected()
        if key is None:
            speak_message(_('Could not load preset: no preset selected.'))
            return
        name = (_(DEFAULT_NAME) if key == DEFAULT_ID else
                self.library.records.get(key, {}).get('name', _('Selected')))
        if self.library.modified(self.dialog.get_working_presentation()) and not self.confirm(
                _('Discard modified presentation settings and load the selected preset?')):
            return
        # Roll back this Load, not the dialog's earlier Apply baseline. The
        # existing owned-leaf transaction also restores native/runtime state.
        rollback = Transaction()
        loaded, reference = self.library.loaded, self.library.reference
        try:
            self.dialog.load_working_presentation(self.library.load(key))
        except (KeyError, ValueError, TypeError, RuntimeError) as error:
            logHandler.log.exception('ClassicSpeech preset load failed')
            self.library.loaded, self.library.reference = loaded, reference
            try:
                rollback.restore()
            finally:
                # A rollback error must still propagate, never become success.
                if key != DEFAULT_ID and key not in self.library.records:
                    reason = _('The selected preset is no longer available.')
                else:
                    reason = str(error)
                message = (_('Could not load {name} preset: {reason}').format(name=name, reason=reason)
                           if reason else _('Could not load {name} preset.').format(name=name))
                speak_message(message)
            return
        if not self.library.read_only:
            self.libraryChanged = True
        self.dialog._markDirty()
        self.refresh_status()
        speak_message(_('{name} preset loaded').format(name=name))

    def prompt_name(self, title, value=''):
        while True:
            dialog = wx.TextEntryDialog(self, _('Preset &name:'), title, value=value)
            try:
                if dialog.ShowModal() != wx.ID_OK:
                    return None
                value = dialog.GetValue()
            finally:
                dialog.Destroy()
            try:
                excluding = self.selected() if title == _('Rename preset') else None
                return self.library.validate_name(value, excluding=excluding)
            except ValueError as error:
                wx.MessageBox(str(error), _('Invalid preset name'), wx.OK | wx.ICON_ERROR, self)

    def onSaveAs(self, event=None):
        if self.library.read_only:
            wx.MessageBox(_('This preset library is read-only because its version is unsupported. '
                            'Its data will be kept unchanged. Use a compatible ClassicSpeech version '
                            'to edit it, or explicitly replace the library.'),
                          _('Cannot save preset'), wx.OK | wx.ICON_ERROR, self)
            return
        name = self.prompt_name(_('Save preset as'))
        if name is None:
            return
        try:
            key = self.library.save_as(name, self.dialog.get_working_presentation())
        except ValueError as error:
            wx.MessageBox(str(error), _('Cannot save preset'), wx.OK | wx.ICON_ERROR, self)
            return
        self.refresh_list(key)
        self.changed()

    def onUpdate(self, event=None):
        key = self.selected()
        if key is None or key == DEFAULT_ID:
            return
        if not self.confirm(_('Replace preset "{name}" with the current presentation settings?').format(
                name=self.library.records[key]['name'])):
            return
        self.library.update(key, self.dialog.get_working_presentation())
        self.changed()

    def onRename(self, event=None):
        key = self.selected()
        if key is None or key == DEFAULT_ID:
            return
        name = self.prompt_name(_('Rename preset'), self.library.records[key]['name'])
        if name is not None:
            self.library.rename(key, name)
            self.refresh_list(key)
            self.changed()

    def onDelete(self, event=None):
        key = self.selected()
        if key is None or key == DEFAULT_ID:
            return
        if self.confirm(_('Delete the selected preset? Current presentation settings will be kept.')):
            self.library.delete(key)
            self.refresh_list()
            self.changed()

    def save_library(self):
        if self.libraryChanged and not self.library.read_only:
            # One base-only scalar, carried by settings_file's existing save boundary.
            # No save_profile_data, config.save, or immediate filesystem writes here.
            _ensure_classic_speech_section()[CONFIG_KEY] = self.library.serialize()
