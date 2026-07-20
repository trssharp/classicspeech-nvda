import wx
import logHandler

log = logHandler.log

class _ClassicSpeechPanelAccessible(wx.Accessible):
	"""Expose panel help text as an object description, matching NVDA settings panels."""

	Window: wx.Window

	def GetRole(self, childId):
		return (wx.ACC_OK, wx.ROLE_SYSTEM_PROPERTYPAGE)

	def GetDescription(self, childId):
		return (wx.ACC_OK, getattr(self.Window, "panelDescription", ""))


def _set_panel_description(panel: wx.Window, title: str, description: str):
	panel.panelDescription = description
	try:
		panel.SetLabel(title.replace("&", "&&"))
	except Exception:
		pass
	try:
		panel.SetAccessible(_ClassicSpeechPanelAccessible(panel))
	except Exception:
		log.exception("ClassicSpeech: failed to set panel accessible description")
