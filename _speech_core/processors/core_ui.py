# _speech_core/processors/core_ui.py
import logHandler

from ..base_processor import BaseSpeechProcessor

log = logHandler.log


class CoreUISpeechProcessor(BaseSpeechProcessor):
	"""Stable addon-facing speech processor entry point.

	Keep this class intentionally thin. The processing engine lives in
	BaseSpeechProcessor; this wrapper gives the addon a future extension point
	without spreading speech logic into classicSpeech.py.
	"""

	def __init__(self):
		super().__init__()
		log.info("CoreUISpeechProcessor loaded")
