# _speech_core/settings package
# Compatibility exports for existing ClassicSpeech imports.

from .constants import *
from .config import (
	get_announce_speech_hook_loaded_enabled,
	get_debug_logging_enabled,
	get_object_navigation_processing_enabled,
	get_query_object_source,
	get_speech_hook_enabled,
	get_speech_hook_loaded_message,
)
from .advanced_panel import AdvancedPanel
from .document_reading_proofing_panel import DocumentReadingProofingPanel
from .dialog import ClassicSpeechDialog
from .hotkeys_panel import HotkeysPanel
from .key_labels_panel import KeyLabelsPanel
from .menus_panel import MenusPanel
from .misc_panel import MiscPanel
from .number_processing_panel import NumberProcessingPanel
from .rename_list_panel import RenameListPanel
from .speech_timing_panel import SpeechTimingPanel
from .token_editor_panel import TokenEditorPanel
from .verbosity_panel import VerbosityPanel
from .web_settings_dialog import WebBrowseSettingsDialog, WebSettingsDialog
from .voice_profiles_dialog import VoiceProfilesDialog

__all__ = [
	"ClassicSpeechDialog",
	"AdvancedPanel",
	"DocumentReadingProofingPanel",
	"HotkeysPanel",
	"KeyLabelsPanel",
	"MenusPanel",
	"MiscPanel",
	"NumberProcessingPanel",
	"RenameListPanel",
	"SpeechTimingPanel",
	"TokenEditorPanel",
	"VerbosityPanel",
	"WebBrowseSettingsDialog",
	"WebSettingsDialog",
	"VoiceProfilesDialog",
	"get_object_navigation_processing_enabled",
	"get_query_object_source",
	"get_speech_hook_enabled",
	"get_announce_speech_hook_loaded_enabled",
	"get_speech_hook_loaded_message",
	"get_debug_logging_enabled",
]
__all__ += [name for name in globals() if name.isupper()]
