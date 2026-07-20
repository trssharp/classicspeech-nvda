"""Snapshot-only dynamic controls for ClassicSpeech Voice Profiles."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProfileSetting:
	setting_id: str
	label: str
	kind: str
	setting: object
	choices: tuple = ()


def _label(setting) -> str:
	return str(getattr(setting, "displayNameWithAccelerator", getattr(setting, "displayName", setting.id)))


def _choice_items(value):
	"""Normalize the public option metadata shapes used by synth drivers.

	NVDA's AutoSettingsMixin normally receives an ordered mapping of
	StringParameterInfo objects. Third-party drivers also expose equivalent
	metadata directly on a setting, commonly as a mapping, an iterable of
	StringParameterInfo objects, or ``(id, displayName)`` pairs. Keep the
	adapter data-driven: no setting or driver names belong here.
	"""
	if value is None:
		return ()
	try:
		items = value.values()
	except AttributeError:
		items = value
	choices = []
	try:
		iterator = iter(items)
	except TypeError:
		return ()
	for item in iterator:
		if isinstance(item, (tuple, list)) and len(item) >= 2:
			item_id, display_name = item[0], item[1]
		else:
			item_id = getattr(item, "id", None)
			display_name = getattr(item, "displayName", None)
		if item_id is None or display_name is None:
			continue
		choices.append((item_id, display_name))
	return tuple(choices)


def _choices_for(driver, setting):
	"""Return choices using NVDA's discovery contract plus generic metadata.

	The first attribute is deliberately the same spelling used by NVDA
	AutoSettingsMixin: ``available{setting.id.capitalize()}s``. This matters for
	camel-case IDs: IBMTTS's ``pauseMode`` and ``sampleRate`` are published as
	``availablePausemodes`` and ``availableSamplerates``. The compatibility
	spelling accepts drivers which preserve interior capitals, and setting-owned
	option metadata makes the snapshot editor useful for equivalent drivers that
	do not publish an availableX property.
	"""
	setting_id = getattr(setting, "id", "")
	attribute_names = (
		f"available{setting_id.capitalize()}s",
		f"available{setting_id[:1].upper()}{setting_id[1:]}s",
	)
	for attribute in attribute_names:
		choices = _choice_items(getattr(driver, attribute, None))
		if choices:
			return choices
	for attribute in ("choices", "options", "availableValues"):
		choices = _choice_items(getattr(setting, attribute, None))
		if choices:
			return choices
	return ()


class VoiceProfileControls:
	"""Adapts ``supportedSettings`` to a mutable profile snapshot, not a driver."""

	def __init__(self, driver, snapshot: dict, on_change):
		self.driver = driver
		self.snapshot = snapshot
		self.on_change = on_change
		self.settings = tuple(self._make_setting(setting) for setting in getattr(driver, "supportedSettings", ()) if self._include(setting))
		self.settings = tuple(setting for setting in self.settings if setting is not None)
		# This is populated only by build(). Retaining the live controls lets a
		# selected voice refresh its inherited dependent values without replacing
		# the Voice combo that raised the change event.
		self._controls_by_setting_id = {}

	def _include(self, setting):
		return bool(getattr(setting, "id", "")) and not setting.id.startswith("_")

	def _make_setting(self, setting):
		if hasattr(setting, "minVal") and hasattr(setting, "maxVal"):
			kind = "numeric"
		elif isinstance(getattr(setting, "defaultVal", None), bool):
			kind = "boolean"
		else:
			choices = _choices_for(self.driver, setting)
			if not choices:
				return None
			return ProfileSetting(setting.id, _label(setting), "choice", setting, choices)
		return ProfileSetting(setting.id, _label(setting), kind, setting)

	def set_value(self, setting_id: str, value) -> None:
		if setting_id not in {setting.setting_id for setting in self.settings}:
			raise KeyError(setting_id)
		self.snapshot[setting_id] = value
		try:
			self.on_change(setting_id, value)
		except TypeError:
			# Keep the original no-argument callback contract available to callers.
			self.on_change()

	def build(self, parent, sizer):
		"""Build wx controls lazily, keeping all event writes inside ``snapshot``."""
		import wx
		from gui import guiHelper, nvdaControls

		helper = guiHelper.BoxSizerHelper(parent, sizer=sizer)
		controls = []
		self._controls_by_setting_id = {}
		for profile_setting in self.settings:
			setting = profile_setting.setting
			if profile_setting.kind == "numeric":
				# Mirror NVDA AutoSettingsMixin's native Voice Settings shape:
				# EnhancedInputSlider, the driver's min/max, and its line/page steps.
				control = helper.addLabeledControl(
					f"{profile_setting.label}:",
					nvdaControls.EnhancedInputSlider,
					minValue=setting.minVal,
					maxValue=setting.maxVal,
				)
				control.SetLineSize(setting.minStep)
				control.SetPageSize(setting.largeStep)
				control.SetValue(int(self.snapshot.get(setting.id, setting.minVal)))
				control.Bind(wx.EVT_SLIDER, lambda evt, item=profile_setting, ctrl=control: self._numeric_changed(evt, item, ctrl))
			elif profile_setting.kind == "boolean":
				control = helper.addItem(wx.CheckBox(parent, label=profile_setting.label))
				control.SetValue(bool(self.snapshot.get(setting.id, False)))
				control.Bind(wx.EVT_CHECKBOX, lambda evt, item=profile_setting: self.set_value(item.setting_id, evt.IsChecked()))
			else:
				control = helper.addLabeledControl(profile_setting.label + ":", wx.Choice, choices=[label for _value, label in profile_setting.choices])
				values = [value for value, _label_text in profile_setting.choices]
				try:
					control.SetSelection(values.index(self.snapshot.get(setting.id)))
				except ValueError:
					control.SetSelection(wx.NOT_FOUND)
				control.Bind(wx.EVT_CHOICE, lambda evt, item=profile_setting, values=values: self.set_value(item.setting_id, values[evt.GetSelection()]))
			control.SetName(profile_setting.label.replace("&", ""))
			controls.append(control)
			self._controls_by_setting_id[profile_setting.setting_id] = control
		return controls

	def refresh_snapshot_values(self, skip_setting_id=None) -> bool:
		"""Refresh built controls from the resolved snapshot without firing edits.

		A voice selection changes the profile's baseline values. Updating the
		existing controls preserves focus on the live Voice combo, so wx and the
		screen reader do not treat it as a newly-created control. Return False
		when this editor no longer matches its supported schema; the dialog can
		then take its existing safe rebuild path.
		"""
		settings_by_id = {setting.setting_id: setting for setting in self.settings}
		for setting_id in settings_by_id:
			if setting_id == skip_setting_id:
				continue
			control = self._controls_by_setting_id.get(setting_id)
			if control is None:
				return False
			try:
				if control.IsBeingDeleted():
					return False
			except AttributeError:
				# Harness controls need only the same setter surface as wx controls.
				pass

		try:
			for setting_id, profile_setting in settings_by_id.items():
				if setting_id == skip_setting_id:
					continue
				control = self._controls_by_setting_id[setting_id]
				setting = profile_setting.setting
				if profile_setting.kind == "numeric":
					control.SetValue(int(self.snapshot.get(setting_id, setting.minVal)))
				elif profile_setting.kind == "boolean":
					control.SetValue(bool(self.snapshot.get(setting_id, False)))
				else:
					values = [value for value, _label_text in profile_setting.choices]
					try:
						selection = values.index(self.snapshot.get(setting_id))
					except ValueError:
						selection = -1
					control.SetSelection(selection)
		except Exception:
			return False
		return True

	def _numeric_changed(self, event, profile_setting, control):
		try:
			self.set_value(profile_setting.setting_id, control.GetValue())
		except Exception:
			# wx emits transient text while an edit is incomplete; retain its last
			# valid snapshot until the next valid value arrives.
			pass
