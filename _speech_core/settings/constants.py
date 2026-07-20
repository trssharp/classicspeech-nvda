PROFILE_NAMES = ["Beginner", "Intermediate", "Advanced"]

HOTKEY_MODE_OFF = "off"
HOTKEY_MODE_DIALOGS = "dialogs"
HOTKEY_MODE_MENUS = "menus"
HOTKEY_MODE_BOTH = "both"
HOTKEY_MODE_CHOICES = [
	("Off", HOTKEY_MODE_OFF),
	("Dialogs", HOTKEY_MODE_DIALOGS),
	("Menus", HOTKEY_MODE_MENUS),
	("Both", HOTKEY_MODE_BOTH),
]

HOTKEY_FORMAT_NATIVE = "native"
HOTKEY_FORMAT_EXPANDED_NO_PLUS = "expandedNoPlus"
HOTKEY_FORMAT_ABBREVIATED_NO_PLUS = "abbreviatedNoPlus"
HOTKEY_FORMAT_CHOICES = [
	("Native shortcut as is", HOTKEY_FORMAT_NATIVE),
	("Expanded without plus", HOTKEY_FORMAT_EXPANDED_NO_PLUS),
	("Abbreviated without plus", HOTKEY_FORMAT_ABBREVIATED_NO_PLUS),
]

HOTKEY_TYPES_ACCESS = "access"
HOTKEY_TYPES_COMMAND = "command"
HOTKEY_TYPES_BOTH = "both"
HOTKEY_TYPES_CHOICES = [
	("Access keys only", HOTKEY_TYPES_ACCESS),
	("Command shortcuts only", HOTKEY_TYPES_COMMAND),
	("Access keys and command shortcuts", HOTKEY_TYPES_BOTH),
]

POSITION_MODE_OFF = "off"
POSITION_MODE_EACH = "each"
POSITION_MODE_FIRST = "first"
POSITION_MODE_CHOICES = [
	("Off", POSITION_MODE_OFF),
	("Announce each item", POSITION_MODE_EACH),
	("Announce only first item", POSITION_MODE_FIRST),
]

QUERY_OBJECT_SOURCE_FOCUS = "focus"
QUERY_OBJECT_SOURCE_NAVIGATOR = "navigator"
QUERY_OBJECT_SOURCE_NATIVE = "native"
QUERY_OBJECT_SOURCE_CHOICES = [
	("NVDA native", QUERY_OBJECT_SOURCE_NATIVE),
	("Focused object", QUERY_OBJECT_SOURCE_FOCUS),
	("Navigator object", QUERY_OBJECT_SOURCE_NAVIGATOR),
]

FALLBACK_SPEECH_DELAY_CHOICES = [250, 500, 750, 1000, 1500, 2000, 3000, 4000]
# Backward-compatible private alias for modules split from the old settings.py.
_FALLBACK_SPEECH_DELAY_CHOICES = FALLBACK_SPEECH_DELAY_CHOICES

PAUSE_MODE_GLOBAL = "global"
PAUSE_MODE_PER_TOKEN = "perToken"

PAUSE_PLACEMENT_AFTER = "after"
PAUSE_PLACEMENT_BEFORE = "before"
PAUSE_PLACEMENT_CHOICES = [
	("Before each token", PAUSE_PLACEMENT_BEFORE),
	("After each token", PAUSE_PLACEMENT_AFTER),
]

PAUSE_CHOICES = [("Off", 0), ("80 ms", 80)] + [(f"{ms} ms", ms) for ms in range(100, 1001, 100)]
GLOBAL_PAUSE_CHOICES = list(PAUSE_CHOICES)

# Token pause values are hybrid overrides. -1 means use the global pause,
# 0 means explicitly no pause for that token, and positive values override global.
TOKEN_PAUSE_USE_GLOBAL = -1
TOKEN_PAUSE_CHOICES = [("Use global", TOKEN_PAUSE_USE_GLOBAL)] + list(PAUSE_CHOICES)

TOKEN_ORDER_ITEMS = [
	("name", "Name"),
	("role", "Role"),
	("value", "Value"),
	("state", "State"),
	("position", "Position"),
	("description", "Description"),
	("hotkey", "Hotkey"),
]
TOKEN_ORDER_LABELS = {tokenKind: label for tokenKind, label in TOKEN_ORDER_ITEMS}
TOKEN_ORDER_KINDS = [tokenKind for tokenKind, _label in TOKEN_ORDER_ITEMS]
