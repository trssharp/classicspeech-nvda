"""ClassicSpeech update checks: GitHub releases, safe downloads and NVDA installation.

No test contacts GitHub: a fake session stands in for the network.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import os
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tests") not in sys.path:
	sys.path.insert(0, str(ROOT / "tests"))

import classic_speech_nvda_master_harness as nvda_harness  # noqa: E402

ADDON_BYTES = b"PK fake add-on"
ADDON_SHA256 = hashlib.sha256(ADDON_BYTES).hexdigest()


def _github_release(tag="v1.08", with_checksum=True, **extra):
	assets = [{
		"name": f"ClassicSpeech-{tag[1:]}.nvda-addon",
		"browser_download_url": f"https://github.com/trssharp/classicspeech-nvda/releases/download/{tag}/addon",
		"size": len(ADDON_BYTES),
	}]
	if with_checksum:
		assets.append({
			"name": f"ClassicSpeech-{tag[1:]}.nvda-addon.sha256",
			"browser_download_url": f"https://github.com/trssharp/classicspeech-nvda/releases/download/{tag}/sha",
		})
	data = {
		"tag_name": tag,
		"name": f"ClassicSpeech {tag[1:]}",
		"body": "## What's new\n\n- **Reset** all settings. See [the guide](https://example.com).\n",
		"html_url": f"https://github.com/trssharp/classicspeech-nvda/releases/tag/{tag}",
		"assets": assets,
	}
	data.update(extra)
	return data


class FakeResponse:
	def __init__(self, status_code=200, data=None, text="", content=b""):
		self.status_code = status_code
		self._data = data
		self.text = text
		self._content = content

	def json(self):
		return self._data

	def iter_content(self, chunk_size=1):
		for start in range(0, len(self._content), 4):
			yield self._content[start:start + 4]

	def __enter__(self):
		return self

	def __exit__(self, *args):
		return False


class FakeSession:
	def __init__(self, responses):
		self.responses = dict(responses)
		self.requests = []

	def get(self, url, **kwargs):
		self.requests.append((url, kwargs))
		response = self.responses[url]
		if isinstance(response, Exception):
			raise response
		return response


class UpdateCheckTests(unittest.TestCase):
	def setUp(self):
		nvda_harness.ClassicSpeechNVDAConfigStartupTests().setUp()
		nvda_harness._import_classic_speech_like_nvda()
		self.updates = importlib.import_module("globalPlugins._speech_core.update_check")
		self.folder = tempfile.mkdtemp()
		self.release = self.updates.release_from_github(_github_release())
		self.wx = sys.modules["wx"]
		self._saved_id_yes = getattr(self.wx, "ID_YES", None)
		self.wx.ID_YES = 5103

	def tearDown(self):
		if self._saved_id_yes is None:
			del self.wx.ID_YES
		else:
			self.wx.ID_YES = self._saved_id_yes
		shutil.rmtree(self.folder, ignore_errors=True)
		nvda_harness._reset_global_plugin_imports()

	def test_repository_comes_from_the_manifest_url(self):
		self.assertEqual(
			self.updates.github_repository("https://github.com/trssharp/classicspeech-nvda"),
			"trssharp/classicspeech-nvda",
		)
		self.assertEqual(self.updates.github_repository("https://github.com/owner/name.git/"), "owner/name")
		self.assertIsNone(self.updates.github_repository(""))
		self.assertIsNone(self.updates.github_repository("https://example.com/owner/name"))

	def test_the_manifest_url_decides_where_updates_come_from(self):
		text = (ROOT / "manifest.ini").read_text(encoding="utf-8")
		url = next(line.split("=", 1)[1].strip().strip('"') for line in text.splitlines() if line.startswith("url"))
		# An empty url turns update checks off; any other url must name a GitHub repository.
		self.assertTrue(url == "" or self.updates.github_repository(url), url)

	def test_versions_compare_as_numbers(self):
		self.assertEqual(self.updates.parse_version("v1.07"), (1, 7))
		self.assertTrue(self.updates.is_newer("1.08", "1.07"))
		self.assertTrue(self.updates.is_newer("v1.10", "1.9"))
		self.assertTrue(self.updates.is_newer("2", "1.99"))
		self.assertFalse(self.updates.is_newer("1.07", "1.07"))
		self.assertFalse(self.updates.is_newer("1.07.0", "1.07"))
		self.assertFalse(self.updates.is_newer("1.06", "1.07"))
		self.assertFalse(self.updates.is_newer("latest", "1.07"))

	def test_release_finds_the_add_on_and_its_checksum(self):
		release = self.release
		self.assertEqual(release.version, "1.08")
		self.assertEqual(release.addon_name, "ClassicSpeech-1.08.nvda-addon")
		self.assertTrue(release.addon_url.endswith("/addon"))
		self.assertTrue(release.checksum_url.endswith("/sha"))
		self.assertIsNone(self.updates.release_from_github(_github_release(prerelease=True)))
		self.assertIsNone(self.updates.release_from_github(_github_release(tag="nightly")))

	def test_checksum_file_and_release_notes_are_read_for_speech(self):
		self.assertEqual(self.updates.checksum_from_file(f"{ADDON_SHA256.upper()}  file.nvda-addon\n"), ADDON_SHA256)
		self.assertIsNone(self.updates.checksum_from_file("not a checksum"))
		notes = self.updates.notes_for_speech(self.release.notes)
		self.assertEqual(notes, "What's new\n\n- Reset all settings. See the guide.")
		self.assertTrue(self.updates.notes_for_speech("word " * 500, limit=40).endswith("..."))

	def test_automatic_checks_run_at_most_once_a_day(self):
		day = self.updates.AUTOMATIC_CHECK_INTERVAL_SECONDS
		self.assertTrue(self.updates.is_due(0, now=10 * day))
		self.assertFalse(self.updates.is_due(10 * day - 60, now=10 * day))
		self.assertTrue(self.updates.is_due(9 * day, now=10 * day))
		self.assertTrue(self.updates.is_due(11 * day, now=10 * day))  # clock turned back
		self.assertTrue(self.updates.is_due("garbage", now=10 * day))

	def test_fetch_reads_the_latest_release_and_explains_failures(self):
		url = self.updates.API_URL.format(repository="trssharp/classicspeech-nvda")
		session = FakeSession({url: FakeResponse(data=_github_release())})
		release = self.updates.fetch_latest_release("1.07", "trssharp/classicspeech-nvda", session=session)
		self.assertEqual(release.version, "1.08")
		headers = session.requests[0][1]["headers"]
		self.assertIn("ClassicSpeech/1.07", headers["User-Agent"])
		for response, text in (
			(FakeResponse(status_code=404), "no ClassicSpeech releases"),
			(FakeResponse(status_code=500), "error 500"),
			(OSError("offline"), "could not be reached"),
		):
			with self.assertRaises(self.updates.UpdateError) as caught:
				self.updates.fetch_latest_release("1.07", "trssharp/classicspeech-nvda", session=FakeSession({url: response}))
			self.assertIn(text, str(caught.exception))

	def _download(self, checksum_text, content=ADDON_BYTES, release=None):
		release = release or self.release
		session = FakeSession({
			release.checksum_url: FakeResponse(text=checksum_text),
			release.addon_url: FakeResponse(content=content),
		})
		return self.updates.download_release(release, "1.07", "trssharp/classicspeech-nvda", self.folder, session=session)

	def test_download_keeps_only_a_file_matching_its_checksum(self):
		path = self._download(f"{ADDON_SHA256}  ClassicSpeech-1.08.nvda-addon")
		self.assertEqual(Path(path).read_bytes(), ADDON_BYTES)
		self.assertEqual(os.path.basename(path), "ClassicSpeech-1.08.nvda-addon")
		os.remove(path)
		with self.assertRaises(self.updates.UpdateError):
			self._download("0" * 64 + "  ClassicSpeech-1.08.nvda-addon")
		self.assertEqual(os.listdir(self.folder), [])

	def test_download_refuses_a_release_without_checksum_or_too_large(self):
		without = self.updates.release_from_github(_github_release(with_checksum=False))
		with self.assertRaises(self.updates.UpdateError):
			self._download("", release=without)
		original = self.updates.MAX_DOWNLOAD_BYTES
		self.updates.MAX_DOWNLOAD_BYTES = 5
		try:
			with self.assertRaises(self.updates.UpdateError):
				self._download(f"{ADDON_SHA256}  x")
		finally:
			self.updates.MAX_DOWNLOAD_BYTES = original
		self.assertEqual(os.listdir(self.folder), [])

	def test_installed_add_on_needs_a_version_and_a_github_page(self):
		saved = sys.modules.get("addonHandler")
		try:
			sys.modules.pop("addonHandler", None)
			self.assertIsNone(self.updates.installed_addon())
			addon_handler = types.ModuleType("addonHandler")
			manifest = {"version": "1.07", "url": "https://github.com/trssharp/classicspeech-nvda"}
			addon_handler.getCodeAddon = lambda *args, **kwargs: types.SimpleNamespace(manifest=manifest)
			sys.modules["addonHandler"] = addon_handler
			self.assertEqual(self.updates.installed_addon(), ("1.07", "trssharp/classicspeech-nvda"))
			manifest["url"] = ""
			self.assertIsNone(self.updates.installed_addon())
		finally:
			if saved is None:
				sys.modules.pop("addonHandler", None)
			else:
				sys.modules["addonHandler"] = saved

	def _checker(self):
		checker = self.updates.UpdateChecker()
		checker.messages = []
		checker.questions = []
		checker.offers = []
		checker.downloads = []
		checker._message = lambda message, wx_icon="information": checker.messages.append(message)

		def offer(summary, notes, question, install_label=""):
			checker.offers.append((summary, notes, question, install_label))
			checker.questions.append(chr(10).join(part for part in (summary, notes, question) if part))
			return 0

		checker._show_offer = offer
		checker._download = lambda release, version, repository: checker.downloads.append(release.version)
		return checker

	def test_a_manual_check_reports_up_to_date_and_errors(self):
		checker = self._checker()
		checker._checked(self.updates.release_from_github(_github_release(tag="v1.07")), "1.07", "o/n", manual=True)
		self.assertIn("ClassicSpeech is up to date", checker.messages[-1])
		checker._checked(self.updates.UpdateError("GitHub could not be reached."), "1.07", "o/n", manual=True)
		self.assertIn("could not check for updates. GitHub could not be reached.", checker.messages[-1])

	def test_a_newer_installed_build_reports_both_versions_without_an_offer(self):
		checker = self._checker()
		release = self.updates.release_from_github(_github_release(tag="v1.01"))
		checker._checked(release, "2.0", "o/n", manual=True)
		self.assertEqual(checker.messages, [
			"You have ClassicSpeech 2.0. The latest published release is 1.01. "
			"Your installed version is newer; no update is available."
		])
		self.assertEqual(checker.offers, [])
		self.assertEqual(checker.downloads, [])

	def test_equivalent_versions_report_up_to_date_not_a_newer_build(self):
		checker = self._checker()
		release = self.updates.release_from_github(_github_release(tag="v2.0.0"))
		checker._checked(release, "2.0", "o/n", manual=True)
		self.assertIn("ClassicSpeech is up to date", checker.messages[0])
		self.assertNotIn("installed version is newer", checker.messages[0])
		self.assertEqual(checker.offers, [])

	def test_an_older_installed_build_is_offered_the_published_update(self):
		checker = self._checker()
		release = self.updates.release_from_github(_github_release(tag="v2.0"))
		checker._checked(release, "1.01", "o/n", manual=True)
		self.assertEqual(checker.messages, [])
		self.assertEqual(len(checker.offers), 1)
		self.assertIn("ClassicSpeech 2.0 is available. You have version 1.01.", checker.offers[0][0])
		self.assertEqual(checker.downloads, [])

	def test_a_newer_installed_build_is_silent_during_automatic_checks(self):
		checker = self._checker()
		release = self.updates.release_from_github(_github_release(tag="v1.01"))
		checker._checked(release, "2.0", "o/n", manual=False)
		self.assertEqual(checker.messages, [])
		self.assertEqual(checker.offers, [])
		self.assertEqual(checker.downloads, [])

	def test_an_automatic_check_is_silent_unless_there_is_an_update(self):
		checker = self._checker()
		checker._checked(self.updates.UpdateError("offline"), "1.07", "o/n", manual=False)
		checker._checked(self.updates.release_from_github(_github_release(tag="v1.07")), "1.07", "o/n", manual=False)
		self.assertEqual(checker.messages, [])
		checker._checked(self.release, "1.07", "o/n", manual=False)
		self.assertEqual(len(checker.questions), 1)
		self.assertIn("ClassicSpeech 1.08 is available. You have version 1.07.", checker.questions[0])
		self.assertIn("Your ClassicSpeech settings are kept.", checker.questions[0])
		self.assertEqual(checker.downloads, [])  # "Not now"

	def test_download_and_install_starts_only_after_the_user_agrees(self):
		checker = self._checker()
		checker._show_offer = lambda summary, notes, question, install_label="": self.wx.ID_YES
		checker._checked(self.release, "1.07", "o/n", manual=True)
		self.assertEqual(checker.downloads, ["1.08"])

	def test_a_downloaded_update_is_handed_to_nvda_and_the_file_removed(self):
		checker = self._checker()
		installed = []
		original = self.updates.install_with_nvda
		self.updates.install_with_nvda = installed.append
		try:
			path = os.path.join(self.folder, "ClassicSpeech-1.08.nvda-addon")
			Path(path).write_bytes(ADDON_BYTES)
			checker._downloaded(path, self.folder)
		finally:
			self.updates.install_with_nvda = original
		self.assertEqual(installed, [path])
		self.assertFalse(os.path.exists(self.folder))

	def test_automatic_checks_follow_the_advanced_setting(self):
		self.assertTrue(self.updates.automatic_checks_enabled())
		self.updates.set_automatic_checks_enabled(False)
		self.assertFalse(self.updates.automatic_checks_enabled())
		import config

		self.assertIs(config.conf.profiles[0]["classicSpeech"]["checkForUpdatesAutomatically"], False)

	def test_no_automatic_check_is_scheduled_outside_an_installed_add_on(self):
		checker = self.updates.UpdateChecker()
		checker.schedule_automatic_check()
		self.assertIsNone(checker._timer)


class UpdateOfferDialogTests(unittest.TestCase):
	"""The What's new section is a box the user can read, not a spoken blob."""

	def setUp(self):
		nvda_harness.ClassicSpeechNVDAConfigStartupTests().setUp()
		nvda_harness._import_classic_speech_like_nvda()
		self.updates = importlib.import_module("globalPlugins._speech_core.update_check")
		self.dialogs = importlib.import_module("globalPlugins._speech_core.update_dialog")
		self.wx = sys.modules["wx"]
		self._saved_id_yes = getattr(self.wx, "ID_YES", None)
		self.wx.ID_YES = 5103

	def tearDown(self):
		if self._saved_id_yes is None:
			del self.wx.ID_YES
		else:
			self.wx.ID_YES = self._saved_id_yes
		nvda_harness._reset_global_plugin_imports()

	def _dialog(self, notes="Line one.\nLine two.", **extra):
		return self.dialogs.UpdateOfferDialog(
			None,
			"ClassicSpeech update",
			"ClassicSpeech 1.11 is available. You have version 1.09.",
			notes,
			**extra,
		)

	def test_the_notes_are_a_read_only_multiline_box(self):
		dialog = self._dialog(install_label="&Download and install")
		style = dialog.notes.ctorKwargs["style"]
		self.assertTrue(style & self.wx.TE_MULTILINE, "the notes must be readable line by line")
		self.assertTrue(style & self.wx.TE_READONLY, "the notes must not be editable")
		self.assertEqual(dialog.notes.ctorKwargs["value"], "Line one.\nLine two.")

	def test_the_box_is_labelled_whats_new(self):
		dialog = self._dialog()
		self.assertIn("What's new", dialog.notes.labelText)

	def test_the_install_button_is_the_default_and_close_is_always_there(self):
		dialog = self._dialog(install_label="&Download and install")
		self.assertIsNotNone(dialog.installButton)
		self.assertEqual(dialog.installButton.ctorKwargs["label"], "&Download and install")
		self.assertIsNotNone(dialog.closeButton)
		# A release with no add-on file has nothing to install.
		self.assertIsNone(self._dialog().installButton)

	def test_the_whole_release_is_shown_not_a_shortened_version(self):
		notes = "word " * 500
		self.assertTrue(self.updates.notes_for_speech(notes, limit=40).endswith("..."))
		self.assertFalse(self.updates.notes_as_text(notes).endswith("..."))

	def test_markdown_is_removed_so_the_box_reads_as_plain_text(self):
		notes = "# ClassicSpeech 1.11\n\n* **Bold** item\n* A [link](https://example.com)\n"
		text = self.updates.notes_as_text(notes)
		self.assertNotIn("#", text)
		self.assertNotIn("**", text)
		self.assertNotIn("https://example.com", text)
		self.assertIn("- Bold item", text)
		self.assertIn("- A link", text)

	def test_an_offer_sends_the_full_notes_and_the_question_to_the_dialog(self):
		checker = self.updates.UpdateChecker()
		shown = []
		checker._show_offer = lambda summary, notes, question, install_label="": shown.append(
			(summary, notes, question, install_label)
		) or 0
		release = self.updates.release_from_github(_github_release())
		checker._offer(release, "1.07", "o/n")
		summary, notes, question, install_label = shown[0]
		self.assertIn("is available", summary)
		self.assertEqual(notes, self.updates.notes_as_text(release.notes))
		self.assertIn("Download and install it now?", question)
		self.assertIn("Download and install", install_label)

	def test_a_release_without_notes_still_says_something_in_the_box(self):
		checker = self.updates.UpdateChecker()
		shown = []
		checker._show_offer = lambda summary, notes, question, install_label="": shown.append(notes) or 0
		checker._offer(self.updates.release_from_github(_github_release(body="")), "1.07", "o/n")
		self.assertTrue(shown[0].strip())


if __name__ == "__main__":
	unittest.main()
