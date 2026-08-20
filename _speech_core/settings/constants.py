from ..localization import _

PROFILE_NAMES = ["Beginner", "Intermediate", "Advanced"]
PROFILE_NAME_CHOICES = [
	(_("Beginner"), "Beginner"),
	(_("Intermediate"), "Intermediate"),
	(_("Advanced"), "Advanced"),
]

HOTKEY_MODE_OFF = "off"
HOTKEY_MODE_DIALOGS = "dialogs"
HOTKEY_MODE_MENUS = "menus"
HOTKEY_MODE_BOTH = "both"
HOTKEY_MODE_CHOICES = [
	(_("Off"), HOTKEY_MODE_OFF),
	(_("Dialogs"), HOTKEY_MODE_DIALOGS),
	(_("Menus"), HOTKEY_MODE_MENUS),
	(_("Both"), HOTKEY_MODE_BOTH),
]

HOTKEY_FORMAT_NATIVE = "native"
HOTKEY_FORMAT_EXPANDED_NO_PLUS = "expandedNoPlus"
HOTKEY_FORMAT_ABBREVIATED_NO_PLUS = "abbreviatedNoPlus"
HOTKEY_FORMAT_CHOICES = [
	(_("Native shortcut as is"), HOTKEY_FORMAT_NATIVE),
	(_("Expanded without plus"), HOTKEY_FORMAT_EXPANDED_NO_PLUS),
	(_("Abbreviated without plus"), HOTKEY_FORMAT_ABBREVIATED_NO_PLUS),
]

HOTKEY_TYPES_ACCESS = "access"
HOTKEY_TYPES_COMMAND = "command"
HOTKEY_TYPES_BOTH = "both"
HOTKEY_TYPES_CHOICES = [
	(_("Access keys only"), HOTKEY_TYPES_ACCESS),
	(_("Command shortcuts only"), HOTKEY_TYPES_COMMAND),
	(_("Access keys and command shortcuts"), HOTKEY_TYPES_BOTH),
]

POSITION_MODE_OFF = "off"
POSITION_MODE_EACH = "each"
POSITION_MODE_FIRST = "first"
POSITION_MODE_CHOICES = [
	(_("Off"), POSITION_MODE_OFF),
	(_("Announce each item"), POSITION_MODE_EACH),
	(_("Announce only first item"), POSITION_MODE_FIRST),
]

QUERY_OBJECT_SOURCE_FOCUS = "focus"
QUERY_OBJECT_SOURCE_NAVIGATOR = "navigator"
QUERY_OBJECT_SOURCE_NATIVE = "native"
QUERY_OBJECT_SOURCE_CHOICES = [
	(_("NVDA native"), QUERY_OBJECT_SOURCE_NATIVE),
	(_("Focused object"), QUERY_OBJECT_SOURCE_FOCUS),
	(_("Navigator object"), QUERY_OBJECT_SOURCE_NAVIGATOR),
]

FALLBACK_SPEECH_DELAY_CHOICES = [250, 500, 750, 1000, 1500, 2000, 3000, 4000]
# Backward-compatible private alias for modules split from the old settings.py.
_FALLBACK_SPEECH_DELAY_CHOICES = FALLBACK_SPEECH_DELAY_CHOICES

PAUSE_MODE_GLOBAL = "global"
PAUSE_MODE_PER_TOKEN = "perToken"

PAUSE_PLACEMENT_AFTER = "after"
PAUSE_PLACEMENT_BEFORE = "before"
PAUSE_PLACEMENT_CHOICES = [
	(_("Before each token"), PAUSE_PLACEMENT_BEFORE),
	(_("After each token"), PAUSE_PLACEMENT_AFTER),
]

PAUSE_CHOICES = [(_("Off"), 0), (_("{ms} ms").format(ms=80), 80)] + [
	(_("{ms} ms").format(ms=ms), ms)
	for ms in range(100, 1001, 100)
]
GLOBAL_PAUSE_CHOICES = list(PAUSE_CHOICES)

# Token pause values are hybrid overrides. -1 means use the global pause,
# 0 means explicitly no pause for that token, and positive values override global.
TOKEN_PAUSE_USE_GLOBAL = -1
TOKEN_PAUSE_CHOICES = [(_("Use global"), TOKEN_PAUSE_USE_GLOBAL)] + list(PAUSE_CHOICES)

TOKEN_ORDER_ITEMS = [
	("name", _("Name")),
	("role", _("Role")),
	("value", _("Value")),
	("state", _("State")),
	("position", _("Position")),
	("description", _("Description")),
	("hotkey", _("Hotkey")),
]
TOKEN_ORDER_LABELS = {tokenKind: label for tokenKind, label in TOKEN_ORDER_ITEMS}
TOKEN_ORDER_KINDS = [tokenKind for tokenKind, _label in TOKEN_ORDER_ITEMS]
