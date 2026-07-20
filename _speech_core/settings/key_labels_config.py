"""Key Labels panel settings helpers."""

import copy

from ..key_labels import apply_key_labels_live, get_key_label_config, save_key_label_config


def _clone_key_label_config():
	return copy.deepcopy(get_key_label_config())


def _save_key_label_config(config_data: dict):
	save_key_label_config(copy.deepcopy(config_data or {}))
	apply_key_labels_live(config_data or {})


def _preview_key_label_config(config_data: dict):
	apply_key_labels_live(copy.deepcopy(config_data or {}))
