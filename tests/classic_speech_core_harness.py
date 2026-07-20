"""ClassicSpeech core regression harness.

Runs outside NVDA with small stubs for the NVDA modules required by the pure
classification / policy / formatting pieces. This is intentionally not a full
headless NVDA harness yet; it protects current v31 behavior while v2 work starts.
"""
from __future__ import annotations

from pathlib import Path
import sys
import types
import unittest
from enum import Enum

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _install_nvda_stubs() -> None:
    class _Log:
        def __init__(self):
            self.messages = []
            self.debug_enabled = False

        def isEnabledFor(self, level):
            return bool(self.debug_enabled and int(level) <= 10)

        def getEffectiveLevel(self):
            return 10 if self.debug_enabled else 20

        def _record(self, level, *args, **kwargs):
            text = " ".join(str(arg) for arg in args)
            self.messages.append((level, text))

        def debug(self, *args, **kwargs):
            self._record("debug", *args, **kwargs)

        def info(self, *args, **kwargs):
            self._record("info", *args, **kwargs)

        def warning(self, *args, **kwargs):
            self._record("warning", *args, **kwargs)

        def error(self, *args, **kwargs):
            self._record("error", *args, **kwargs)

        def exception(self, *args, **kwargs):
            self._record("exception", *args, **kwargs)

        def debugWarning(self, *args, **kwargs):
            self._record("debugWarning", *args, **kwargs)

    log_handler = types.ModuleType("logHandler")
    log_handler.log = _Log()
    sys.modules.setdefault("logHandler", log_handler)

    control_types = types.ModuleType("controlTypes")
    role_mod = types.ModuleType("controlTypes.role")
    state_mod = types.ModuleType("controlTypes.state")

    class Role(Enum):
        BUTTON = 1
        COMBOBOX = 2
        CHECKBOX = 3
        RADIOBUTTON = 4
        MENUITEM = 5
        EDITABLETEXT = 6
        STATICTEXT = 7
        LIST = 8
        LISTITEM = 9
        TREEVIEW = 10
        TREEVIEWITEM = 11
        MENU = 12
        MENUBAR = 13
        TABLE = 14
        TABLECELL = 15
        TAB = 16
        TABCONTROL = 17
        DIALOG = 18
        DOCUMENT = 19
        UNKNOWN = 20

    class State(Enum):
        COLLAPSED = 1
        EXPANDED = 2
        CHECKED = 3
        HALFCHECKED = 4
        PRESSED = 5
        SELECTED = 6
        ON = 7
        INDETERMINATE = 8

    role_mod._roleLabels = {
        Role.BUTTON: "button",
        Role.COMBOBOX: "combo box",
        Role.CHECKBOX: "check box",
        Role.RADIOBUTTON: "radio button",
        Role.MENUITEM: "menu item",
        Role.EDITABLETEXT: "edit",
        Role.STATICTEXT: "text",
        Role.LIST: "list",
        Role.LISTITEM: "list item",
        Role.TREEVIEW: "tree view",
        Role.TREEVIEWITEM: "tree view item",
        Role.MENU: "menu",
        Role.MENUBAR: "menu bar",
        Role.TABLE: "table",
        Role.TABLECELL: "cell",
        Role.TAB: "tab",
        Role.TABCONTROL: "tab control",
        Role.DIALOG: "dialog",
        Role.DOCUMENT: "document",
        Role.UNKNOWN: "unknown",
    }
    state_mod._stateLabels = {
        State.COLLAPSED: "collapsed",
        State.EXPANDED: "expanded",
        State.CHECKED: "checked",
        State.HALFCHECKED: "half checked",
        State.PRESSED: "pressed",
        State.SELECTED: "selected",
        State.ON: "on",
        State.INDETERMINATE: "indeterminate",
    }
    state_mod._negativeStateLabels = {
        State.CHECKED: "not checked",
        State.PRESSED: "not pressed",
        State.SELECTED: "not selected",
        State.ON: "off",
    }
    control_types.Role = Role
    control_types.State = State
    control_types.role = role_mod
    control_types.state = state_mod
    sys.modules.setdefault("controlTypes", control_types)
    sys.modules.setdefault("controlTypes.role", role_mod)
    sys.modules.setdefault("controlTypes.state", state_mod)

    api_mod = types.ModuleType("api")
    api_mod.clipboard = []

    def copy_to_clip(text, notify=True):
        api_mod.clipboard.append(str(text))
        return True

    api_mod.copyToClip = copy_to_clip
    api_mod.getFocusObject = lambda: None
    sys.modules.setdefault("api", api_mod)

    ui_mod = types.ModuleType("ui")
    ui_mod.messages = []
    ui_mod.message = lambda text: ui_mod.messages.append(str(text))
    sys.modules.setdefault("ui", ui_mod)

    speech_mod = types.ModuleType("speech")
    commands_mod = types.ModuleType("speech.commands")

    class BreakCommand:
        def __init__(self, time=0):
            self.time = time

        def __repr__(self):
            return f"BreakCommand(time={self.time!r})"

    class CharacterModeCommand:
        def __init__(self, state):
            self.state = bool(state)

        def __repr__(self):
            return f"CharacterModeCommand({self.state!r})"

    class EndUtteranceCommand:
        pass

    class IndexCommand:
        def __init__(self, index):
            self.index = index

    class _ProsodyCommand:
        def __init__(self, offset=0, multiplier=1):
            self.offset = offset
            self.multiplier = multiplier
            self.isDefault = offset == 0 and multiplier == 1

    class PitchCommand(_ProsodyCommand):
        pass

    class RateCommand(_ProsodyCommand):
        pass

    class VolumeCommand(_ProsodyCommand):
        pass

    class SuppressUnicodeNormalizationCommand:
        pass

    commands_mod.BreakCommand = BreakCommand
    commands_mod.CharacterModeCommand = CharacterModeCommand
    commands_mod.EndUtteranceCommand = EndUtteranceCommand
    commands_mod.IndexCommand = IndexCommand
    commands_mod.PitchCommand = PitchCommand
    commands_mod.RateCommand = RateCommand
    commands_mod.VolumeCommand = VolumeCommand
    commands_mod.SuppressUnicodeNormalizationCommand = SuppressUnicodeNormalizationCommand
    speech_mod.commands = commands_mod
    speech_mod.speak_calls = []

    def speak(sequence, *args, **kwargs):
        speech_mod.speak_calls.append(list(sequence))

    speech_mod.speak = speak

    shortcut_keys_mod = types.ModuleType("speech.shortcutKeys")
    shortcut_keys_mod.speakKeyboardShortcuts = lambda *args, **kwargs: None
    speech_mod.shortcutKeys = shortcut_keys_mod

    class _ExtensionPoint:
        def __init__(self):
            self.callbacks = []

        def register(self, callback):
            self.callbacks.append(callback)

        def unregister(self, callback):
            if callback in self.callbacks:
                self.callbacks.remove(callback)

    extensions_mod = types.ModuleType("speech.extensions")
    extensions_mod.filter_speechSequence = _ExtensionPoint()
    speech_mod.extensions = extensions_mod

    priorities_mod = types.ModuleType("speech.priorities")
    priorities_mod.Spri = types.SimpleNamespace(NEXT="next", NORMAL="normal")
    speech_mod.priorities = priorities_mod

    speech_manager_mod = types.ModuleType("speech.manager")
    speech_manager_mod._shouldCancelExpiredFocusEvents = lambda *args, **kwargs: True
    speech_manager_mod.SpeechManager = type("SpeechManager", (), {})
    speech_mod.manager = speech_manager_mod

    say_all_mod = types.ModuleType("speech.sayAll")
    say_all_mod.SayAllHandler = types.SimpleNamespace(isRunning=lambda: False)
    speech_mod.sayAll = say_all_mod

    sys.modules.setdefault("speech", speech_mod)
    sys.modules.setdefault("speech.commands", commands_mod)
    sys.modules.setdefault("speech.shortcutKeys", shortcut_keys_mod)
    sys.modules.setdefault("speech.extensions", extensions_mod)
    sys.modules.setdefault("speech.priorities", priorities_mod)
    sys.modules.setdefault("speech.manager", speech_manager_mod)
    sys.modules.setdefault("speech.sayAll", say_all_mod)

    core_mod = types.ModuleType("core")
    core_mod.callLater = lambda delay, func, *args, **kwargs: func(*args, **kwargs)
    sys.modules.setdefault("core", core_mod)

    config_mod = types.ModuleType("config")

    class _Section(dict):
        pass

    class _BaseConfig(dict):
        def validate(self, *args, **kwargs):
            return True

    class _Config(dict):
        def __init__(self):
            super().__init__()
            self.BASE_ONLY_SECTIONS = set()
            self.spec = {}
            self.validator = object()
            self.profiles = [self]
            self["classicSpeech"] = {
                "defaultProfile": "Beginner",
                "speechHookEnabled": True,
                "debugLogging": False,
                "profileData": {},
                "profileBehaviorData": {},
                "textProcessingData": {
                    "announceNewLinesDuringSayAll": False,
                    "newLineMessage": "new line",
                    "splitMixedCaseWords": False,
                    "suppressWordInternalDashes": False,
                    "spellAlphanumericData": "off",
                    "listItemStateReporting": "notSelected",
                    "repeatedCharacterMode": "3",
                    "filterRepeatedCharacters": False,
                    "repeatedCharacterLimit": 3,
                },
                "shapeData": {},
                "keyLabelData": {"renames": {}, "mutedLabels": []},
            }
            self["presentation"] = {
                "reportKeyboardShortcuts": True,
                "reportObjectPositionInformation": True,
                "guessObjectPositionInformationWhenUnavailable": False,
                "reportObjectDescriptions": True,
                "reportTooltips": False,
            }

    config_mod.conf = _Config()
    config_mod._transformSpec = lambda spec: spec
    sys.modules.setdefault("config", config_mod)

    class _WxObject:
        def __init__(self, *args, **kwargs):
            pass

        def __getattr__(self, name):
            def _method(*args, **kwargs):
                if name.startswith("Get"):
                    return 0
                return None
            return _method

    wx_mod = types.ModuleType("wx")
    for name, value in {
        "ACC_OK": 0,
        "ROLE_SYSTEM_PROPERTYPAGE": 0,
        "DEFAULT_DIALOG_STYLE": 0,
        "RESIZE_BORDER": 0,
        "MAXIMIZE_BOX": 0,
        "LC_REPORT": 0,
        "LC_SINGLE_SEL": 0,
        "LC_NO_HEADER": 0,
        "TAB_TRAVERSAL": 0,
        "BORDER_THEME": 0,
        "LB_SINGLE": 0,
        "VERTICAL": 0,
        "HORIZONTAL": 0,
        "ALL": 0,
        "EXPAND": 0,
        "LEFT": 0,
        "RIGHT": 0,
        "TOP": 0,
        "BOTTOM": 0,
        "ALIGN_CENTER_VERTICAL": 0,
        "ID_OK": 5100,
        "ID_CANCEL": 5101,
        "YES": 1,
        "YES_NO": 0,
        "NO_DEFAULT": 0,
        "ICON_QUESTION": 0,
        "NOT_FOUND": -1,
        "WXK_DELETE": 127,
        "WXK_F2": 344,
        "WXK_UP": 315,
        "WXK_DOWN": 317,
        "EVT_LISTBOX": object(),
        "EVT_CHECKLISTBOX": object(),
        "EVT_KEY_DOWN": object(),
        "EVT_CONTEXT_MENU": object(),
        "EVT_CHOICE": object(),
        "EVT_CHECKBOX": object(),
        "EVT_TEXT": object(),
        "EVT_BUTTON": object(),
        "EVT_CLOSE": object(),
        "EVT_LIST_ITEM_FOCUSED": object(),
    }.items():
        setattr(wx_mod, name, value)
    for cls_name in (
        "Accessible", "Dialog", "Panel", "Window", "BoxSizer", "FlexGridSizer",
        "GridSizer", "StaticText", "Choice", "CheckBox", "TextCtrl", "Button",
        "ListCtrl", "ListBox", "CheckListBox", "Menu", "TextEntryDialog",
    ):
        setattr(wx_mod, cls_name, type(cls_name, (_WxObject,), {}))
    wx_mod.CallAfter = lambda func, *args, **kwargs: func(*args, **kwargs)
    wx_mod.CallLater = lambda *args, **kwargs: types.SimpleNamespace(Stop=lambda: None)
    wx_mod.MessageBox = lambda *args, **kwargs: 0
    wx_mod.Bell = lambda: None
    wx_lib_mod = types.ModuleType("wx.lib")
    scrolledpanel_mod = types.ModuleType("wx.lib.scrolledpanel")
    scrolledpanel_mod.ScrolledPanel = type("ScrolledPanel", (_WxObject,), {})
    wx_lib_mod.scrolledpanel = scrolledpanel_mod
    wx_mod.lib = wx_lib_mod
    sys.modules.setdefault("wx", wx_mod)
    sys.modules.setdefault("wx.lib", wx_lib_mod)
    sys.modules.setdefault("wx.lib.scrolledpanel", scrolledpanel_mod)

    gui_mod = types.ModuleType("gui")
    gui_mod.mainFrame = types.SimpleNamespace(prePopup=lambda: None, postPopup=lambda: None)
    nvda_controls_mod = types.SimpleNamespace(
        AutoWidthColumnListCtrl=wx_mod.ListCtrl,
        CustomCheckListBox=wx_mod.CheckListBox,
    )

    class _BoxSizerHelper:
        def __init__(self, parent, sizer=None):
            self.parent = parent
            self.sizer = sizer or wx_mod.BoxSizer()

        def addItem(self, item, *args, **kwargs):
            return item

        def addLabeledControl(self, label, controlClass, *args, **kwargs):
            control = controlClass(self.parent, *args, **kwargs)
            if hasattr(control, "SetName"):
                control.SetName(str(label).replace("&", "").rstrip(":"))
            return control

    gui_helper_mod = types.SimpleNamespace(BoxSizerHelper=_BoxSizerHelper)
    gui_mod.nvdaControls = nvda_controls_mod
    gui_mod.guiHelper = gui_helper_mod
    sys.modules.setdefault("gui", gui_mod)

    global_plugin_handler_mod = types.ModuleType("globalPluginHandler")
    global_plugin_handler_mod.runningPlugins = []
    global_plugin_handler_mod.GlobalPlugin = type("GlobalPlugin", (), {"__init__": lambda self: None})
    sys.modules.setdefault("globalPluginHandler", global_plugin_handler_mod)

    global_commands_mod = types.ModuleType("globalCommands")
    global_commands_mod.commands = types.SimpleNamespace(script_reportCurrentFocus=lambda gesture=None: None)
    sys.modules.setdefault("globalCommands", global_commands_mod)

    queue_handler_mod = types.ModuleType("queueHandler")
    queue_handler_mod.eventQueue = []
    queue_handler_mod.queueFunction = lambda queue, func, *args, **kwargs: func(*args, **kwargs)
    sys.modules.setdefault("queueHandler", queue_handler_mod)

    script_handler_mod = types.ModuleType("scriptHandler")
    script_handler_mod.script = lambda **kwargs: (lambda func: func)
    script_handler_mod.getCurrentScript = lambda: None
    script_handler_mod.getLastScriptRepeatCount = lambda: 0
    sys.modules.setdefault("scriptHandler", script_handler_mod)

    input_core_mod = types.ModuleType("inputCore")
    input_core_mod.manager = types.SimpleNamespace(isInputHelpActive=False)
    sys.modules.setdefault("inputCore", input_core_mod)

    for module_name in ("braille", "browseMode", "textInfos", "keyLabels", "vkCodes"):
        sys.modules.setdefault(module_name, types.ModuleType(module_name))
    sys.modules["textInfos"].POSITION_SELECTION = object()
    sys.modules["keyLabels"].localizedKeyLabels = {}
    sys.modules["vkCodes"].byName = {}


_install_nvda_stubs()

from speech.commands import BreakCommand, CharacterModeCommand

import api
import config

from _speech_core.base_classifier import classify_tokens
from _speech_core.base_processor import BaseSpeechProcessor
from _speech_core.formatter import SpeechFormatter
from _speech_core.history import sequence_to_text
from _speech_core.processors.text import TextProcessor

from _speech_core.hotkey_extractor import (
    parse_shortcut_list,
    parse_trailing_label_shortcut,
)
from _speech_core.token_policy import apply_token_policy
from _speech_core.tokens import (
    TOKEN_HOTKEY,
    TOKEN_NAME,
    TOKEN_POSITION,
    TOKEN_ROLE,
    TOKEN_STATE,
    TOKEN_VALUE,
    token,
)

DEFAULT_PROFILE = {
    "enabledTokens": {
        TOKEN_NAME: True,
        TOKEN_ROLE: True,
        TOKEN_VALUE: True,
        TOKEN_STATE: True,
        TOKEN_POSITION: True,
        "description": True,
        "tooltip": False,
        TOKEN_HOTKEY: True,
    },
    "pauseMode": "global",
    "globalPause": 80,
    "order": [TOKEN_NAME, TOKEN_ROLE, TOKEN_VALUE, TOKEN_STATE, TOKEN_POSITION, "description", "tooltip", TOKEN_HOTKEY],
    "renames": {},
    "mutedLabels": [],
    "pauses": {},
    "pauseAfterFinalToken": False,
    "pausePlacement": "before",
}


class PluginStartupTests(unittest.TestCase):
    def test_global_plugin_imports_like_nvda_startup(self):
        import importlib

        package = types.ModuleType("globalPlugins")
        package.__path__ = [str(ROOT)]
        sys.modules["globalPlugins"] = package
        for name in list(sys.modules):
            if name == "globalPlugins.classicSpeech" or name.startswith("globalPlugins._speech_core"):
                del sys.modules[name]
        module = importlib.import_module("globalPlugins.classicSpeech")
        plugin = module.GlobalPlugin()
        try:
            self.assertTrue(hasattr(plugin, "processor"))
        finally:
            plugin.terminate()


class BaseProcessorExtractionTests(unittest.TestCase):
    def tearDown(self):
        api.getFocusObject = lambda: None
        config.conf["classicSpeech"]["textProcessingData"]["listItemStateReporting"] = "notSelected"

    def test_position_mode_first_suppresses_repeated_container_position(self):
        processor = BaseSpeechProcessor()
        parent = types.SimpleNamespace(
            role=types.SimpleNamespace(name="LIST"),
            name="Items",
            windowHandle=100,
            IAccessibleChildID=0,
            parent=None,
        )
        focus = types.SimpleNamespace(
            role=types.SimpleNamespace(name="LISTITEM"),
            name="Alpha",
            windowHandle=101,
            IAccessibleChildID=1,
            parent=parent,
        )
        api.getFocusObject = lambda: focus
        first = [token(TOKEN_NAME, raw=["Alpha"], spoken="Alpha"), token(TOKEN_POSITION, raw="1 of 2", spoken="1 of 2")]
        second = [token(TOKEN_NAME, raw=["Beta"], spoken="Beta"), token(TOKEN_POSITION, raw="2 of 2", spoken="2 of 2")]

        self.assertTrue(any(tok.kind == TOKEN_POSITION for tok in processor._apply_position_mode(first, mode_override="first")))
        self.assertFalse(any(tok.kind == TOKEN_POSITION for tok in processor._apply_position_mode(second, mode_override="first")))

    def test_object_token_builder_reads_safe_query_tokens(self):
        processor = BaseSpeechProcessor()
        obj = types.SimpleNamespace(
            name="OK",
            value="",
            role=types.SimpleNamespace(name="BUTTON", displayString="button"),
            states=[types.SimpleNamespace(name="selected", displayString="selected")],
            positionInfo={"indexInGroup": 1, "similarItemsInGroup": 2},
            keyboardShortcut="Alt+O",
            description="Accepts the dialog",
        )
        kinds = [tok.kind for tok in processor._build_query_tokens_for_object(obj)]
        self.assertIn(TOKEN_NAME, kinds)
        self.assertIn(TOKEN_ROLE, kinds)
        self.assertIn(TOKEN_STATE, kinds)
        self.assertIn(TOKEN_POSITION, kinds)
        self.assertIn(TOKEN_HOTKEY, kinds)

    def test_list_item_state_reporting_defaults_to_not_selected_only(self):
        processor = BaseSpeechProcessor()
        focus = types.SimpleNamespace(role=types.SimpleNamespace(name="LISTITEM"), parent=None)
        api.getFocusObject = lambda: focus
        tokens = processor._restore_native_item_state_order([
            token(TOKEN_NAME, raw=["Alpha"], spoken="Alpha"),
            token(TOKEN_STATE, raw="selected", spoken="selected"),
            token(TOKEN_STATE, raw="selected", spoken="not selected"),
        ])
        out = SpeechFormatter().format(tokens, profile_config=DEFAULT_PROFILE)
        text_items = [item for item in out if isinstance(item, str)]
        self.assertEqual(text_items, ["Alpha", "not selected"])

    def test_token_editor_default_order_keeps_value_before_state(self):
        processor = BaseSpeechProcessor()
        focus = types.SimpleNamespace(role=types.SimpleNamespace(name="LISTITEM"), parent=None)
        api.getFocusObject = lambda: focus
        tokens = processor._restore_native_item_state_order([
            token(TOKEN_NAME, raw=["Items View"], spoken="Items View"),
            token(TOKEN_ROLE, raw="list", spoken="list view"),
            token(TOKEN_STATE, raw="not selected", spoken="not selected"),
            token(TOKEN_VALUE, raw="DSpeech", spoken="DSpeech"),
            token(TOKEN_POSITION, raw="1 of 14", spoken="1 of 14"),
        ])
        out = SpeechFormatter().format(tokens, profile_config=DEFAULT_PROFILE)
        text_items = [item for item in out if isinstance(item, str)]
        self.assertEqual(text_items, ["Items View", "list view", "DSpeech", "not selected", "1 of 14"])

    def test_token_editor_can_place_state_before_value(self):
        profile = {
            **DEFAULT_PROFILE,
            "order": [TOKEN_NAME, TOKEN_ROLE, TOKEN_STATE, TOKEN_VALUE, TOKEN_POSITION, "description", "tooltip", TOKEN_HOTKEY],
        }
        out = SpeechFormatter().format([
            token(TOKEN_NAME, raw=["Items View"], spoken="Items View"),
            token(TOKEN_ROLE, raw="list", spoken="list view"),
            token(TOKEN_STATE, raw="not selected", spoken="not selected"),
            token(TOKEN_VALUE, raw="$Recycle.Bin", spoken="$Recycle.Bin"),
            token(TOKEN_POSITION, raw="1 of 32", spoken="1 of 32"),
        ], profile_config=profile)
        text_items = [item for item in out if isinstance(item, str)]
        self.assertEqual(text_items, ["Items View", "list view", "not selected", "$Recycle.Bin", "1 of 32"])

    def test_list_item_state_reporting_native_leaves_token_order_unchanged(self):
        config.conf["classicSpeech"]["textProcessingData"]["listItemStateReporting"] = "native"
        processor = BaseSpeechProcessor()
        focus = types.SimpleNamespace(role=types.SimpleNamespace(name="LISTITEM"), parent=None)
        api.getFocusObject = lambda: focus
        tokens = [
            token(TOKEN_STATE, raw="not selected", spoken="not selected"),
            token(TOKEN_NAME, raw=["Alpha"], spoken="Alpha"),
        ]
        self.assertEqual(processor._restore_native_item_state_order(tokens), tokens)

    def test_state_only_selected_change_still_speaks_focused_item_value(self):
        config.conf["classicSpeech"]["textProcessingData"]["listItemStateReporting"] = "notSelected"
        processor = BaseSpeechProcessor()
        processor.verbosity.get_profile_config = lambda: DEFAULT_PROFILE
        focus = types.SimpleNamespace(
            role=types.SimpleNamespace(name="LISTITEM"),
            parent=types.SimpleNamespace(role=types.SimpleNamespace(name="LIST"), parent=None),
            name="DSpeech",
            value="",
            treeInterceptor=None,
        )
        api.getFocusObject = lambda: focus
        sequence = ["selected"]
        processor.process(sequence)
        self.assertEqual([item for item in sequence if isinstance(item, str)], ["DSpeech"])

    def test_state_only_not_selected_change_speaks_item_value_and_allowed_state(self):
        config.conf["classicSpeech"]["textProcessingData"]["listItemStateReporting"] = "notSelected"
        processor = BaseSpeechProcessor()
        processor.verbosity.get_profile_config = lambda: DEFAULT_PROFILE
        focus = types.SimpleNamespace(
            role=types.SimpleNamespace(name="LISTITEM"),
            parent=types.SimpleNamespace(role=types.SimpleNamespace(name="LIST"), parent=None),
            name="DSpeech",
            value="",
            treeInterceptor=None,
        )
        api.getFocusObject = lambda: focus
        sequence = ["not selected"]
        processor.process(sequence)
        self.assertEqual([item for item in sequence if isinstance(item, str)], ["DSpeech", "not selected"])


class TokenPolicyTests(unittest.TestCase):
    def test_editable_blank_value_and_selected_state_are_suppressed(self):
        tokens, pending = apply_token_policy(
            [
                token(TOKEN_ROLE, raw="editableText", spoken="edit"),
                token(TOKEN_VALUE, raw="blank", spoken="blank"),
                token(TOKEN_STATE, raw="selected", spoken="selected"),
            ],
            focus_role_key="editabletext",
            selected_text="",
        )
        self.assertIsNone(pending)
        self.assertEqual([tok.kind for tok in tokens], [TOKEN_ROLE])

    def test_editable_selected_text_becomes_value(self):
        tokens, pending = apply_token_policy(
            [
                token(TOKEN_ROLE, raw="editableText", spoken="edit"),
                token(TOKEN_VALUE, raw="blank", spoken="blank"),
                token(TOKEN_STATE, raw="selected", spoken="selected"),
            ],
            focus_role_key="editabletext",
            selected_text="Untitled.txt",
        )
        self.assertIsNone(pending)
        values = [tok.text() for tok in tokens if tok.kind == TOKEN_VALUE]
        self.assertEqual(values, ["Untitled.txt"])

    def test_edit_combo_classifies_as_single_role_for_token_editor(self):
        for spoken_variant in ("edit combo", "editable combo", "editablecombo"):
            with self.subTest(spoken_variant=spoken_variant):
                tokens = classify_tokens(["File name", spoken_variant, "selected report.docx"])
                self.assertEqual([tok.kind for tok in tokens], [TOKEN_NAME, TOKEN_ROLE, TOKEN_VALUE])
                self.assertEqual(tokens[1].raw, "editcombo")
                self.assertEqual(tokens[1].text(), "edit combo")

    def test_editable_focus_combo_box_role_promotes_to_edit_combo(self):
        processor = BaseSpeechProcessor()
        combo_parent = types.SimpleNamespace(role=types.SimpleNamespace(name="COMBOBOX"), parent=None)
        focus = types.SimpleNamespace(
            role=types.SimpleNamespace(name="EDITABLETEXT"),
            parent=combo_parent,
            name="File name",
            value="",
            treeInterceptor=None,
        )
        api.getFocusObject = lambda: focus
        sequence = ["File name:", "combo box", "collapsed", "Alt+n"]
        processor.process(sequence)
        text_items = [item for item in sequence if isinstance(item, str)]
        self.assertIn("edit combo", text_items)
        self.assertNotIn("combo box", text_items)
        self.assertNotIn("collapsed", text_items)

    def test_combo_box_expansion_state_is_suppressed_without_muting_other_states(self):
        processor = BaseSpeechProcessor()
        focus = types.SimpleNamespace(
            role=types.SimpleNamespace(name="COMBOBOX"),
            parent=None,
            name="Style",
            value="Normal",
            treeInterceptor=None,
        )
        api.getFocusObject = lambda: focus
        sequence = ["Style", "combo box", "collapsed", "Normal"]
        processor.process(sequence)
        text_items = [item for item in sequence if isinstance(item, str)]
        self.assertIn("combo box", text_items)
        self.assertNotIn("collapsed", text_items)

    def test_combo_box_state_only_change_speech_reports_natively(self):
        processor = BaseSpeechProcessor()
        focus = types.SimpleNamespace(
            role=types.SimpleNamespace(name="COMBOBOX"),
            parent=None,
            name="Style",
            value="Normal",
            treeInterceptor=None,
        )
        api.getFocusObject = lambda: focus
        sequence = ["expanded"]
        processor.process(sequence)
        text_items = [item for item in sequence if isinstance(item, str)]
        self.assertEqual(text_items, ["expanded"])

    def test_non_combo_expansion_state_still_speaks(self):
        processor = BaseSpeechProcessor()
        focus = types.SimpleNamespace(
            role=types.SimpleNamespace(name="TREEVIEWITEM"),
            parent=types.SimpleNamespace(role=types.SimpleNamespace(name="TREEVIEW"), parent=None),
            name="Folder",
            value="",
            treeInterceptor=None,
        )
        api.getFocusObject = lambda: focus
        sequence = ["Folder", "tree view item", "expanded"]
        processor.process(sequence)
        text_items = [item for item in sequence if isinstance(item, str)]
        self.assertIn("expanded", text_items)

    def test_edit_combo_selected_prefixed_value_is_normalized(self):
        tokens, pending = apply_token_policy(
            [
                token(TOKEN_ROLE, raw="editcombo", spoken="edit combo"),
                token(TOKEN_VALUE, raw="selected report.docx", spoken="selected report.docx"),
            ],
            focus_role_key="editabletext",
            selected_text="",
        )
        self.assertIsNone(pending)
        self.assertEqual([tok.text() for tok in tokens if tok.kind == TOKEN_VALUE], ["report.docx"])

    def test_edit_combo_focus_uses_editable_value_policy(self):
        tokens, pending = apply_token_policy(
            [
                token(TOKEN_ROLE, raw="editcombo", spoken="edit combo"),
                token(TOKEN_VALUE, raw="blank", spoken="blank"),
                token(TOKEN_STATE, raw="selected", spoken="selected"),
            ],
            focus_role_key="editcombo",
            selected_text="Chosen item",
        )
        self.assertIsNone(pending)
        self.assertEqual([tok.text() for tok in tokens if tok.kind == TOKEN_VALUE], ["Chosen item"])

    def test_hotkey_only_sequence_is_deferred_then_appended_to_content(self):
        no_content, pending = apply_token_policy([token(TOKEN_HOTKEY, raw="Ctrl+N", spoken="Ctrl+N")])
        self.assertEqual(no_content, [])
        self.assertTrue(pending)

        content, pending = apply_token_policy([token(TOKEN_NAME, raw=["New"], spoken="New")], pending_hotkey=pending)
        self.assertIsNone(pending)
        self.assertEqual([tok.kind for tok in content], [TOKEN_NAME, TOKEN_HOTKEY])
        self.assertEqual(content[-1].text(), "Ctrl+N")


class BaseProcessorDebugLoggingTests(unittest.TestCase):
    def setUp(self):
        import logHandler

        logHandler.log.messages.clear()
        logHandler.log.debug_enabled = False
        config.conf["classicSpeech"]["debugLogging"] = False

    def tearDown(self):
        import logHandler

        logHandler.log.messages.clear()
        logHandler.log.debug_enabled = False
        config.conf["classicSpeech"]["debugLogging"] = False

    def test_base_processor_debug_logging_is_quiet_by_default(self):
        import logHandler

        BaseSpeechProcessor().hotkeys._apply_hotkey_mode([], "dialog")
        self.assertFalse(any("Hotkey filtering" in text for _level, text in logHandler.log.messages))

    def test_base_processor_debug_logging_respects_advanced_setting(self):
        import logHandler

        config.conf["classicSpeech"]["debugLogging"] = True
        BaseSpeechProcessor().hotkeys._apply_hotkey_mode([], "dialog")
        self.assertTrue(any("Hotkey filtering" in text for _level, text in logHandler.log.messages))

    def test_base_processor_debug_logging_respects_nvda_debug_mode(self):
        import logHandler

        logHandler.log.debug_enabled = True
        BaseSpeechProcessor().hotkeys._apply_hotkey_mode([], "dialog")
        self.assertTrue(any("Hotkey filtering" in text for _level, text in logHandler.log.messages))


class FormatterTests(unittest.TestCase):
    def test_default_global_pause_emits_between_tokens_and_after_final(self):
        profile = dict(DEFAULT_PROFILE)
        profile.pop("pauses", None)
        profile["pauseAfterFinalToken"] = True
        out = SpeechFormatter().format(
            [token(TOKEN_NAME, spoken="OK"), token(TOKEN_ROLE, spoken="button")],
            profile_config=profile,
        )
        self.assertEqual([item for item in out if isinstance(item, str)], ["OK", "button"])
        self.assertEqual([item.time for item in out if isinstance(item, BreakCommand)], [80, 80])

    def test_explicit_zero_pause_still_disables_global_pause_for_token(self):
        profile = dict(DEFAULT_PROFILE)
        profile.update({"pauses": {TOKEN_NAME: 0, TOKEN_ROLE: 0}, "pauseAfterFinalToken": True})
        out = SpeechFormatter().format(
            [token(TOKEN_NAME, spoken="OK"), token(TOKEN_ROLE, spoken="button")],
            profile_config=profile,
        )
        self.assertEqual(out, ["OK", "button"])

    def test_formatter_honors_order_renames_mutes_and_breaks(self):
        profile = dict(DEFAULT_PROFILE)
        profile.update(
            {
                "order": [TOKEN_ROLE, TOKEN_NAME, TOKEN_STATE],
                "renames": {"button": "btn", "checked": "on"},
                "pauses": {TOKEN_ROLE: -1, TOKEN_NAME: -1, TOKEN_STATE: -1},
                "pauseAfterFinalToken": True,

            }
        )
        out = SpeechFormatter().format(
            [
                token(TOKEN_NAME, raw=["OK"], spoken="OK"),
                token(TOKEN_ROLE, raw="button", spoken="button"),
                token(TOKEN_STATE, raw="checked", spoken="checked"),
            ],
            profile_config=profile,
        )
        text_items = [item for item in out if isinstance(item, str)]
        break_count = sum(isinstance(item, BreakCommand) for item in out)
        self.assertEqual(text_items, ["btn", "OK", "on"])
        self.assertEqual(break_count, 3)

    def test_formatter_renders_value_tokens_literally(self):
        out = SpeechFormatter().format([token(TOKEN_VALUE, raw="Ctrl+N", spoken="Ctrl+N")], profile_config=DEFAULT_PROFILE)
        self.assertEqual(out, ["Ctrl+N"])


class HistoryHelpersTests(unittest.TestCase):
    def test_sequence_to_text_ignores_commands(self):
        self.assertEqual(sequence_to_text(["Save", BreakCommand(time=80), "button"]), "Save button")


if __name__ == "__main__":
    unittest.main(verbosity=2)
