"""Check GitHub for a newer ClassicSpeech, download it and install it with NVDA.

ClassicSpeech releases are published on the GitHub repository named by the
``url`` in the add-on's manifest, such as
https://github.com/trssharp/classicspeech-nvda. With an empty ``url``, update
checks are off. A check asks GitHub for the latest release and compares its
tag, such as v1.08, with the installed version.

When the release is newer, ClassicSpeech offers to download its .nvda-addon
file. The download must match the release's .sha256 file. Then NVDA's own
add-on installation takes over: it asks the user to confirm, installs the new
version in place of this one, keeping ClassicSpeech's settings, and offers to
restart NVDA.

Checks run in the background. An automatic check runs at most once a day, a
little after NVDA starts, and speaks up only when there is an update.
"""
from __future__ import annotations

import contextlib
import hashlib
import os
import re
import shutil
import tempfile
import threading
import time
from dataclasses import dataclass

from .localization import _

API_URL = "https://api.github.com/repos/{repository}/releases/latest"
RELEASES_URL = "https://github.com/{repository}/releases"
CHECK_TIMEOUT_SECONDS = 20
DOWNLOAD_TIMEOUT_SECONDS = (20, 120)
MAX_DOWNLOAD_BYTES = 50 * 1024 * 1024
AUTOMATIC_CHECK_DELAY_MS = 30 * 1000
AUTOMATIC_CHECK_INTERVAL_SECONDS = 24 * 60 * 60
ADDON_EXTENSION = ".nvda-addon"
CHECKSUM_EXTENSION = ".sha256"
NOTES_LIMIT = 1200

_GITHUB_REPOSITORY = re.compile(r"^https?://(?:www\.)?github\.com/([\w.-]+)/([\w.-]+?)(?:\.git)?/?$", re.IGNORECASE)
_CHECKSUM = re.compile(r"^[0-9a-fA-F]{64}$")


class UpdateError(Exception):
	"""A check or download failed; the message can be shown to the user."""


@dataclass(frozen=True)
class Release:
	version: str
	name: str
	notes: str
	page_url: str
	addon_name: str = ""
	addon_url: str = ""
	addon_size: int = 0
	checksum_url: str = ""


# -- pure helpers ---------------------------------------------------------------

def github_repository(url):
	"""Return ``owner/name`` for a GitHub repository URL, otherwise None."""
	match = _GITHUB_REPOSITORY.match(str(url or "").strip())
	if not match:
		return None
	return f"{match.group(1)}/{match.group(2)}"


def parse_version(text):
	"""Return a version such as ``1.07`` or ``v1.07`` as a tuple of numbers, or None."""
	text = str(text or "").strip()
	if text[:1] in ("v", "V"):
		text = text[1:]
	parts = text.split(".")
	if not text or not all(part.isdigit() for part in parts):
		return None
	return tuple(int(part) for part in parts)


def is_newer(candidate, installed):
	"""True when version text ``candidate`` is newer than ``installed``."""
	new, old = parse_version(candidate), parse_version(installed)
	if new is None or old is None:
		return False
	width = max(len(new), len(old))
	return new + (0,) * (width - len(new)) > old + (0,) * (width - len(old))


def release_from_github(data):
	"""Return the Release described by GitHub's JSON for a release, or None."""
	if not isinstance(data, dict) or data.get("draft") or data.get("prerelease"):
		return None
	tag = str(data.get("tag_name") or "")
	version = tag[1:] if tag[:1] in ("v", "V") else tag
	if parse_version(version) is None:
		return None
	addon, checksum = None, None
	assets = [asset for asset in data.get("assets") or () if isinstance(asset, dict)]
	for asset in assets:
		if str(asset.get("name") or "").lower().endswith(ADDON_EXTENSION):
			addon = asset
			break
	if addon is not None:
		wanted = str(addon.get("name")) + CHECKSUM_EXTENSION
		checksum = next((asset for asset in assets if asset.get("name") == wanted), None)
	return Release(
		version=version,
		name=str(data.get("name") or f"ClassicSpeech {version}"),
		notes=str(data.get("body") or ""),
		page_url=str(data.get("html_url") or ""),
		addon_name=str(addon.get("name") or "") if addon else "",
		addon_url=str(addon.get("browser_download_url") or "") if addon else "",
		addon_size=int(addon.get("size") or 0) if addon else 0,
		checksum_url=str(checksum.get("browser_download_url") or "") if checksum else "",
	)


def checksum_from_file(text):
	"""Return the SHA-256 in a ``.sha256`` file (``<hex>  <file name>``), or None."""
	words = str(text or "").split()
	if words and _CHECKSUM.match(words[0]):
		return words[0].lower()
	return None


def notes_as_text(notes, limit=None):
	"""Return release notes as plain text, shortened to ``limit`` characters.

	Markdown headings, list bullets, emphasis and link targets are removed, so
	what is left reads the same in a box as it does out loud. Without a limit
	the whole release is kept, which is what the read-only box shows.
	"""
	text = str(notes or "").replace("\r\n", "\n")
	text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
	text = re.sub(r"(?m)^[ \t]{0,3}#{1,6}[ \t]*", "", text)
	text = re.sub(r"(?m)^[ \t]*[-*+][ \t]+", "- ", text)
	text = text.replace("**", "").replace("__", "").replace("`", "")
	text = re.sub(r"\n{3,}", "\n\n", text).strip()
	if limit is not None and len(text) > limit:
		text = text[:limit].rsplit(" ", 1)[0].rstrip() + "..."
	return text


def notes_for_speech(notes, limit=NOTES_LIMIT):
	"""Release notes shortened for somewhere the user cannot scroll."""
	return notes_as_text(notes, limit=limit)


def is_due(last_check, now=None, interval=AUTOMATIC_CHECK_INTERVAL_SECONDS):
	"""True when an automatic check is due, ``last_check`` being seconds since the epoch."""
	now = time.time() if now is None else now
	try:
		last_check = float(last_check)
	except (TypeError, ValueError):
		return True
	return last_check <= 0 or now - last_check >= interval or last_check > now


# -- the running add-on -----------------------------------------------------------

def installed_addon():
	"""Return ``(version, repository)`` for this ClassicSpeech, or None when not installed as an add-on."""
	try:
		import addonHandler

		manifest = addonHandler.getCodeAddon().manifest
		version = str(manifest["version"])
		repository = github_repository(manifest.get("url"))
	except Exception:
		return None
	if not repository or parse_version(version) is None:
		return None
	return version, repository


# -- network ----------------------------------------------------------------------

def _requests():
	try:
		import requests
	except Exception as error:
		raise UpdateError(_("NVDA's internet support is not available.")) from error
	return requests


def _headers(version, repository):
	return {
		"Accept": "application/vnd.github+json",
		"User-Agent": f"ClassicSpeech/{version} (NVDA add-on; +https://github.com/{repository})",
	}


def fetch_latest_release(version, repository, session=None):
	"""Ask GitHub for the latest release. Raises UpdateError."""
	getter = session or _requests()
	try:
		response = getter.get(
			API_URL.format(repository=repository),
			headers=_headers(version, repository),
			timeout=CHECK_TIMEOUT_SECONDS,
		)
	except Exception as error:
		raise UpdateError(_("GitHub could not be reached. Check your internet connection.")) from error
	if response.status_code == 404:
		raise UpdateError(_("There are no ClassicSpeech releases on GitHub yet."))
	if response.status_code != 200:
		raise UpdateError(_("GitHub answered with error {code}.").format(code=response.status_code))
	try:
		release = release_from_github(response.json())
	except Exception as error:
		raise UpdateError(_("GitHub's answer could not be read.")) from error
	if release is None:
		raise UpdateError(_("The latest release on GitHub has no version number ClassicSpeech understands."))
	return release


def download_release(release, version, repository, folder, session=None):
	"""Download the release's add-on file into ``folder`` and check it. Returns its path.

	Raises UpdateError when the download fails, is too large, or does not
	match the release's checksum file.
	"""
	if not release.addon_url:
		raise UpdateError(_("The release has no add-on file."))
	if not release.checksum_url:
		raise UpdateError(_("The release has no checksum file, so its add-on file can't be checked."))
	if release.addon_size > MAX_DOWNLOAD_BYTES:
		raise UpdateError(_("The add-on file is larger than expected."))
	getter = session or _requests()
	headers = _headers(version, repository)
	name = os.path.basename(release.addon_name) or "ClassicSpeech" + ADDON_EXTENSION
	if not name.lower().endswith(ADDON_EXTENSION):
		name += ADDON_EXTENSION
	path = os.path.join(folder, name)
	try:
		response = getter.get(release.checksum_url, headers=headers, timeout=CHECK_TIMEOUT_SECONDS)
		expected = checksum_from_file(response.text) if response.status_code == 200 else None
	except Exception as error:
		raise UpdateError(_("The checksum file could not be downloaded.")) from error
	if expected is None:
		raise UpdateError(_("The checksum file could not be read."))
	digest = hashlib.sha256()
	size = 0
	try:
		with getter.get(release.addon_url, headers=headers, stream=True, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response:
			if response.status_code != 200:
				raise UpdateError(_("GitHub answered with error {code}.").format(code=response.status_code))
			with open(path, "wb") as stream:
				for chunk in response.iter_content(chunk_size=128 * 1024):
					if not chunk:
						continue
					size += len(chunk)
					if size > MAX_DOWNLOAD_BYTES:
						raise UpdateError(_("The add-on file is larger than expected."))
					digest.update(chunk)
					stream.write(chunk)
	except UpdateError:
		with contextlib.suppress(OSError):
			os.remove(path)
		raise
	except Exception as error:
		with contextlib.suppress(OSError):
			os.remove(path)
		raise UpdateError(_("The add-on file could not be downloaded.")) from error
	if digest.hexdigest() != expected:
		with contextlib.suppress(OSError):
			os.remove(path)
		raise UpdateError(_("The downloaded file does not match its checksum, so it was deleted."))
	return path


# -- settings -----------------------------------------------------------------------

def automatic_checks_enabled():
	from .settings.config_core import _as_bool, _read_classic_speech_section

	try:
		return _as_bool(_read_classic_speech_section().get("checkForUpdatesAutomatically", True), True)
	except Exception:
		return True


def set_automatic_checks_enabled(enabled):
	from .settings.config_core import _ensure_classic_speech_section

	_ensure_classic_speech_section()["checkForUpdatesAutomatically"] = bool(enabled)


def _last_check():
	from .settings.config_core import _read_classic_speech_section

	try:
		return int(_read_classic_speech_section().get("lastUpdateCheck", 0))
	except Exception:
		return 0


def _remember_check(now=None):
	from .settings.config_core import _ensure_classic_speech_section

	with contextlib.suppress(Exception):
		_ensure_classic_speech_section()["lastUpdateCheck"] = int(time.time() if now is None else now)


# -- checking from NVDA --------------------------------------------------------------

class UpdateChecker:
	"""Runs checks and downloads in the background and talks to the user in NVDA."""

	def __init__(self):
		self._busy = False
		self._stopped = False
		self._timer = None

	def stop(self):
		self._stopped = True
		timer, self._timer = self._timer, None
		if timer is not None:
			with contextlib.suppress(Exception):
				timer.Stop()

	def schedule_automatic_check(self):
		"""Check a little after NVDA starts, if automatic checks are on and a day has passed."""
		if installed_addon() is None or _is_secure() or not automatic_checks_enabled() or not is_due(_last_check()):
			return
		import wx

		self._timer = wx.CallLater(AUTOMATIC_CHECK_DELAY_MS, self.check, manual=False)

	def check(self, manual=True):
		self._timer = None
		if self._stopped or self._busy:
			return
		addon = installed_addon()
		if addon is None:
			if manual:
				# Never block the caller, which may be NVDA's core queue: see _message.
				import wx

				wx.CallAfter(
					self._message,
					_("This copy of ClassicSpeech doesn't know where its updates are published, so it can't check for them."),
					wx_icon="error",
				)
			return
		if not manual and not automatic_checks_enabled():
			return
		version, repository = addon
		self._busy = True
		if manual:
			from .message_priority import speak_message

			speak_message(_("Checking for ClassicSpeech updates"))
		self._run(lambda: fetch_latest_release(version, repository), lambda outcome: self._checked(outcome, version, repository, manual))

	def _run(self, work, done):
		"""Run ``work`` in a background thread, then ``done(result or UpdateError)`` in NVDA's main thread."""
		import wx

		def target():
			try:
				outcome = work()
			except UpdateError as error:
				outcome = error
			except Exception as error:
				_log().debug("ClassicSpeech update check failed", exc_info=True)
				outcome = UpdateError(str(error) or error.__class__.__name__)
			wx.CallAfter(done, outcome)

		threading.Thread(target=target, name="ClassicSpeechUpdates", daemon=True).start()

	def _checked(self, outcome, version, repository, manual):
		self._busy = False
		if self._stopped:
			return
		if isinstance(outcome, UpdateError):
			_log().info("ClassicSpeech: update check failed: %s", outcome)
			if manual:
				self._message(
					_("ClassicSpeech could not check for updates. {reason}").format(reason=outcome),
					wx_icon="error",
				)
			return
		_remember_check()
		release = outcome
		if not is_newer(release.version, version):
			if manual:
				if is_newer(version, release.version):
					message = _(
						"You have ClassicSpeech {version}. The latest published release is {latest}. "
						"Your installed version is newer; no update is available."
					).format(version=version, latest=release.version)
				else:
					message = _(
						"ClassicSpeech is up to date. You have version {version}, the latest release."
					).format(version=version)
				self._message(message)
			return
		self._offer(release, version, repository)

	def _offer(self, release, version, repository):
		import wx

		summary = _("ClassicSpeech {new} is available. You have version {installed}.").format(
			new=release.version,
			installed=version,
		)
		notes = notes_as_text(release.notes)
		if not notes:
			# Translators: Shown in the What's new box for a release with no notes.
			notes = _("This release has no notes.")
		if not release.addon_url:
			self._show_offer(
				summary,
				notes,
				_("This release has no add-on file to install. Download it from {url}").format(
					url=release.page_url or RELEASES_URL.format(repository=repository)
				),
			)
			return
		answer = self._show_offer(
			summary,
			notes,
			_(
				"Download and install it now? NVDA asks you to confirm the installation, "
				"then offers to restart. Your ClassicSpeech settings are kept."
			),
			install_label=_("&Download and install"),
		)
		if answer != wx.ID_YES:
			return
		self._download(release, version, repository)

	def _show_offer(self, summary, notes, question, install_label=""):
		"""Show what is available and what is new in it, the notes in a box to read.

		It waits for the user, so it runs only from wx's event loop
		(``wx.CallAfter``), never inside NVDA's core queue, which it would freeze.
		"""
		from .update_dialog import show_update_offer

		return show_update_offer(
			_("ClassicSpeech update"),
			summary,
			notes,
			question=question,
			install_label=install_label,
			close_label=_("&Not now") if install_label else _("&Close"),
		)

	def _download(self, release, version, repository):
		from .message_priority import speak_message

		folder = tempfile.mkdtemp(prefix="ClassicSpeech-update-")
		self._busy = True
		speak_message(_("Downloading ClassicSpeech {version}").format(version=release.version))
		self._run(
			lambda: download_release(release, version, repository, folder),
			lambda outcome: self._downloaded(outcome, folder),
		)

	def _downloaded(self, outcome, folder):
		self._busy = False
		try:
			if self._stopped:
				return
			if isinstance(outcome, UpdateError):
				_log().info("ClassicSpeech: update download failed: %s", outcome)
				self._message(
					_("ClassicSpeech could not download the update. {reason}").format(reason=outcome),
					wx_icon="error",
				)
				return
			try:
				install_with_nvda(outcome)
			except Exception:
				self._message(
					_("NVDA could not install the update. Details are in the NVDA log."),
					wx_icon="error",
				)
		finally:
			# NVDA has copied the add-on into its add-ons folder, or the install was cancelled.
			shutil.rmtree(folder, ignore_errors=True)

	def _message(self, message, wx_icon="information"):
		"""Show a message box. It waits for the user, so it runs only from wx's event loop
		(``wx.CallAfter``), never inside NVDA's core queue, which it would freeze."""
		import gui
		import wx

		icon = wx.ICON_ERROR if wx_icon == "error" else wx.ICON_INFORMATION
		gui.mainFrame.prePopup()
		try:
			wx.MessageBox(message, _("ClassicSpeech update"), wx.OK | icon, gui.mainFrame)
		finally:
			gui.mainFrame.postPopup()

def install_with_nvda(path):
	"""Hand a downloaded add-on file to NVDA, which confirms, installs and offers a restart."""
	try:
		from gui import addonGui

		addonGui.handleRemoteAddonInstall(path)
	except Exception:
		_log().error("ClassicSpeech: NVDA could not install %s", path, exc_info=True)
		raise


def _is_secure():
	try:
		import globalVars

		return bool(getattr(globalVars.appArgs, "secure", False))
	except Exception:
		return False


def _log():
	import logHandler

	return logHandler.log
