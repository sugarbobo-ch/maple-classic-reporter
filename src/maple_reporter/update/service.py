"""Background GitHub release discovery and download orchestration."""

from __future__ import annotations

import json
import hashlib
import heapq
import logging
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import zipfile
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable

import requests

from maple_reporter import __version__
from maple_reporter.update.manifest import SemVer, canonical_json, safe_relative_path, sha256_file, verify_ed25519
from maple_reporter.utils.config import get_base_dir, get_user_app_data_dir

LOGGER = logging.getLogger(__name__)

GITHUB_OWNER = "sugarbobo-ch"
GITHUB_REPOSITORY = "maple-classic-reporter"
GITHUB_RELEASES_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPOSITORY}/releases"
FULL_ASSET_PATTERN = re.compile(r"^MapleClassicReporter-v(?P<version>.+)-windows-x64\.zip$")
DELTA_ASSET_PATTERN = re.compile(
    r"^MapleClassicReporter-v(?P<from>.+)-to-v(?P<to>.+)-windows-x64\.patch\.zip$"
)
CHECK_INTERVAL_SECONDS = 6 * 60 * 60
MAX_UPDATE_CACHE_BYTES = 5 * 1024 * 1024
UPDATE_PUBLIC_KEY_ENV = "MAPLE_REPORTER_UPDATE_PUBLIC_KEY"
EMBEDDED_UPDATE_PUBLIC_KEY = "G2nZipsLXsnILUl80j4UR+6z01D6D8HyvvmLT+Yk4Qs="


class UpdateState(str, Enum):
    IDLE = "idle"
    CHECKING = "checking"
    UP_TO_DATE = "up_to_date"
    AVAILABLE = "available"
    DOWNLOADING = "downloading"
    READY = "ready"
    WAITING_FOR_IDLE = "waiting_for_idle"
    APPLYING = "applying"
    UPDATED = "updated"
    ERROR = "error"
    INSUFFICIENT_SPACE = "insufficient_space"


@dataclass
class ReleaseAsset:
    name: str
    url: str
    size: int = 0
    digest: str = ""
    kind: str = "full"
    from_version: str | None = None
    to_version: str | None = None
    required_bytes: int = 0


@dataclass
class ReleaseCandidate:
    version: str
    prerelease: bool
    release_url: str
    body: str
    published_at: str = ""
    assets: list[ReleaseAsset] = field(default_factory=list)
    manifest_url: str = ""
    signature_url: str = ""


def _now() -> float:
    return time.time()


def _configured_public_key() -> str:
    configured = os.environ.get(UPDATE_PUBLIC_KEY_ENV)
    if configured is not None:
        return configured.strip()
    return EMBEDDED_UPDATE_PUBLIC_KEY if getattr(sys, "frozen", False) else ""


def _asset_digest(value: Any) -> str:
    text = str(value or "")
    return text.split(":", 1)[1] if text.startswith("sha256:") else text


def _release_candidate(raw: dict[str, Any]) -> ReleaseCandidate | None:
    tag = str(raw.get("tag_name") or "").strip()
    if not tag:
        return None
    try:
        version = str(SemVer.parse(tag))
    except ValueError:
        return None
    assets: list[ReleaseAsset] = []
    manifest_url = ""
    signature_url = ""
    for raw_asset in raw.get("assets", []) or []:
        if not isinstance(raw_asset, dict):
            continue
        name = str(raw_asset.get("name") or "")
        url = str(raw_asset.get("browser_download_url") or "")
        if not name or not url:
            continue
        if name == "update-manifest-v1.json":
            manifest_url = url
            continue
        if name == "update-manifest-v1.json.sig":
            signature_url = url
            continue
        full_match = FULL_ASSET_PATTERN.match(name)
        delta_match = DELTA_ASSET_PATTERN.match(name)
        if not full_match and not delta_match:
            continue
        assets.append(
            ReleaseAsset(
                name=name,
                url=url,
                size=int(raw_asset.get("size") or 0),
                digest=_asset_digest(raw_asset.get("digest")),
                kind="delta" if delta_match else "full",
                from_version=delta_match.group("from") if delta_match else None,
                to_version=delta_match.group("to") if delta_match else full_match.group("version"),
            )
        )
    return ReleaseCandidate(
        version=version,
        prerelease=bool(raw.get("prerelease")),
        release_url=str(raw.get("html_url") or ""),
        body=str(raw.get("body") or ""),
        published_at=str(raw.get("published_at") or ""),
        assets=assets,
        manifest_url=manifest_url,
        signature_url=signature_url,
    )


class UpdateService:
    """Own update state, network work and the hand-off to the bundled updater."""

    def __init__(
        self,
        *,
        emit_event: Callable[[str, Any], None],
        get_config: Callable[[], dict[str, Any]],
        is_busy: Callable[[], bool],
        close_app: Callable[[], None] | None = None,
        session: requests.Session | None = None,
        install_dir: Path | None = None,
        update_dir: Path | None = None,
    ) -> None:
        self._emit_event = emit_event
        self._get_config = get_config
        self._is_busy = is_busy
        self._close_app = close_app
        self._session = session or requests.Session()
        self._install_dir = (install_dir or get_base_dir()).resolve()
        self._apply_enabled = bool(getattr(sys, "frozen", False) or os.environ.get("MAPLE_REPORTER_ENABLE_UPDATES") == "1")
        self._update_dir = (update_dir or (get_user_app_data_dir() / "updates")).resolve()
        self._update_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._cancel = threading.Event()
        self._check_thread: threading.Thread | None = None
        self._download_thread: threading.Thread | None = None
        self._apply_thread: threading.Thread | None = None
        self._candidate: ReleaseCandidate | None = None
        self._releases: list[ReleaseCandidate] = []
        self._asset: ReleaseAsset | None = None
        self._download_assets: list[ReleaseAsset] = []
        self._package_path: Path | None = None
        self._last_check = 0.0
        self._status: dict[str, Any] = self._default_status()
        self._load_cache()
        self._cleanup_stale_cache()

    def _default_status(self) -> dict[str, Any]:
        return {
            "state": UpdateState.IDLE.value,
            "current_version": __version__,
            "target_version": None,
            "downloaded_bytes": 0,
            "total_bytes": 0,
            "progress_percent": 0,
            "package_kind": None,
            "release_notes": "",
            "release_url": "",
            "required_bytes": 0,
            "available_bytes": 0,
            "error_code": None,
            "error_message": None,
        }

    @property
    def update_dir(self) -> Path:
        return self._update_dir

    def status(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._status)

    def _set_status(self, state: UpdateState, **updates: Any) -> None:
        with self._lock:
            self._status.update(state=state.value, **updates)
            snapshot = dict(self._status)
        self._emit_event("UPDATE_STATUS", snapshot)

    def _load_cache(self) -> None:
        path = self._update_dir / "release-cache.json"
        try:
            cached = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(cached, dict):
                self._last_check = float(cached.get("checked_at") or 0)
                releases_raw = cached.get("releases", [])
                if isinstance(releases_raw, list):
                    self._releases = [
                        ReleaseCandidate(
                            version=str(r.get("version")),
                            prerelease=bool(r.get("prerelease")),
                            release_url=str(r.get("release_url") or ""),
                            body=str(r.get("body") or ""),
                            published_at=str(r.get("published_at") or ""),
                            assets=[ReleaseAsset(**asset) for asset in r.get("assets", [])],
                            manifest_url=str(r.get("manifest_url") or ""),
                            signature_url=str(r.get("signature_url") or ""),
                        )
                        for r in releases_raw
                        if isinstance(r, dict)
                    ]
                candidate_raw = cached.get("candidate")
                if isinstance(candidate_raw, dict):
                    self._candidate = ReleaseCandidate(
                        version=str(candidate_raw.get("version")),
                        prerelease=bool(candidate_raw.get("prerelease")),
                        release_url=str(candidate_raw.get("release_url") or ""),
                        body=str(candidate_raw.get("body") or ""),
                        published_at=str(candidate_raw.get("published_at") or ""),
                        assets=[ReleaseAsset(**asset) for asset in candidate_raw.get("assets", [])],
                        manifest_url=str(candidate_raw.get("manifest_url") or ""),
                        signature_url=str(candidate_raw.get("signature_url") or ""),
                    )
                    self._select_assets_for_candidate(self._releases or [self._candidate])
        except (OSError, ValueError, TypeError, KeyError):
            return

    def _save_cache(self, releases: list[ReleaseCandidate]) -> None:
        path = self._update_dir / "release-cache.json"
        serialised = {
            "checked_at": self._last_check,
            "etag": getattr(self, "_etag", ""),
            "releases": [self._candidate_dict(release) for release in releases[:30]],
            "candidate": self._candidate_dict(self._candidate) if self._candidate else None,
        }
        path.write_text(json.dumps(serialised, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _candidate_dict(candidate: ReleaseCandidate | None) -> dict[str, Any] | None:
        if not candidate:
            return None
        return {
            "version": candidate.version,
            "prerelease": candidate.prerelease,
            "release_url": candidate.release_url,
            "body": candidate.body,
            "published_at": candidate.published_at,
            "assets": [asset.__dict__ for asset in candidate.assets],
            "manifest_url": candidate.manifest_url,
            "signature_url": candidate.signature_url,
        }

    def _cleanup_stale_cache(self) -> None:
        try:
            for path in self._update_dir.iterdir():
                if path.name in {"release-cache.json", "pending-update.json"}:
                    continue
                if path.is_file() and path.stat().st_size > MAX_UPDATE_CACHE_BYTES:
                    path.unlink(missing_ok=True)
                elif path.is_file() and _now() - path.stat().st_mtime > 7 * 24 * 3600:
                    path.unlink(missing_ok=True)
                elif path.is_dir() and _now() - path.stat().st_mtime > 7 * 24 * 3600:
                    shutil.rmtree(path, ignore_errors=True)
        except OSError:
            LOGGER.debug("Unable to clean stale update cache", exc_info=True)

    def start_check(self, force: bool = False) -> bool:
        with self._lock:
            if self._check_thread and self._check_thread.is_alive():
                return False
            if self._download_thread and self._download_thread.is_alive():
                return False
            if self._status.get("state") in {
                UpdateState.DOWNLOADING.value,
                UpdateState.APPLYING.value,
                UpdateState.WAITING_FOR_IDLE.value,
            }:
                return False
            if not force and _now() - self._last_check < CHECK_INTERVAL_SECONDS:
                if self._candidate and self._candidate.version != __version__:
                    self._select_asset_for_candidate()
                    self._set_status(
                        UpdateState.AVAILABLE,
                        target_version=self._candidate.version,
                        release_notes=self._candidate.body,
                        release_url=self._candidate.release_url,
                        package_kind="delta" if all(asset.kind == "delta" for asset in self._download_assets) else (self._asset.kind if self._asset else "full"),
                        total_bytes=sum(asset.size for asset in self._download_assets),
                        required_bytes=sum(asset.required_bytes for asset in self._download_assets),
                    )
                    self._maybe_auto_download()
                return True
            self._cancel.clear()
            self._check_thread = threading.Thread(target=self._check_worker, daemon=True, name="update-check")
            self._check_thread.start()
            return True

    def _check_worker(self) -> None:
        self._set_status(UpdateState.CHECKING, error_code=None, error_message=None)
        try:
            config = self._get_config() or {}
            channel = str(config.get("update_channel") or "preview")
            if channel not in {"stable", "preview"}:
                channel = "preview"
            response = self._session.get(
                GITHUB_RELEASES_URL,
                params={"per_page": "30"},
                headers={
                    "Accept": "application/vnd.github+json",
                    "User-Agent": "MapleClassicReporter-Updater",
                },
                timeout=(8, 20),
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, list):
                raise ValueError("GitHub releases response was not a list")
            releases = [candidate for raw in payload if isinstance(raw, dict) and (candidate := _release_candidate(raw))]
            current = SemVer.parse(__version__)
            eligible = [candidate for candidate in releases if channel == "preview" or not candidate.prerelease]
            eligible = [candidate for candidate in eligible if SemVer.parse(candidate.version) > current]
            self._candidate = max(eligible, key=lambda candidate: SemVer.parse(candidate.version), default=None)
            self._last_check = _now()
            self._releases = releases
            self._save_cache(releases)
            if not self._candidate:
                self._set_status(UpdateState.UP_TO_DATE, target_version=None, release_notes="", release_url="")
                return
            self._select_assets_for_candidate(releases)
            if not self._asset:
                raise ValueError("The selected GitHub release has no Windows x64 package")
            self._verify_candidate_manifest()
            self._set_status(
                UpdateState.AVAILABLE,
                target_version=self._candidate.version,
                release_notes=self._candidate.body,
                release_url=self._candidate.release_url,
                package_kind="delta" if all(asset.kind == "delta" for asset in self._download_assets) else self._asset.kind,
                total_bytes=sum(asset.size for asset in self._download_assets),
                required_bytes=sum(asset.required_bytes for asset in self._download_assets),
            )
            self._maybe_auto_download()
        except Exception as error:
            LOGGER.warning("Update check failed: %s", error)
            self._set_status(UpdateState.ERROR, error_code="check_failed", error_message=str(error))

    def _select_asset_for_candidate(self) -> None:
        self._select_assets_for_candidate(self._releases or ([self._candidate] if self._candidate else []))

    def _set_asset_space_requirement(self, asset: ReleaseAsset) -> None:
        if getattr(sys, "frozen", False):
            current_size = sum(path.stat().st_size for path in self._install_dir.rglob("*") if path.is_file()) if self._install_dir.is_dir() else 0
        else:
            current_size = 0
        asset.required_bytes = asset.required_bytes or asset.size + (
            current_size if asset.kind == "full" else max(1, current_size // 10)
        ) + 64 * 1024 * 1024

    def _select_assets_for_candidate(self, releases: list[ReleaseCandidate]) -> None:
        if not self._candidate:
            self._asset = None
            self._download_assets = []
            return
        current = str(SemVer.parse(__version__))
        target = self._candidate.version
        eligible_edges: dict[str, list[ReleaseAsset]] = {}
        for release in releases:
            for asset in release.assets:
                if asset.kind != "delta" or not asset.from_version or not asset.to_version:
                    continue
                try:
                    from_version = str(SemVer.parse(asset.from_version))
                    to_version = str(SemVer.parse(asset.to_version))
                    if SemVer.parse(to_version) <= SemVer.parse(from_version) or SemVer.parse(to_version) > SemVer.parse(target):
                        continue
                except ValueError:
                    continue
                eligible_edges.setdefault(from_version, []).append(asset)

        # Dijkstra by download size. This handles a user who has skipped several
        # releases while preferring a smaller patch chain over a full archive.
        queue: list[tuple[int, int, int, str, list[ReleaseAsset]]] = [(0, 0, 0, current, [])]
        best: dict[str, tuple[int, int]] = {current: (0, 0)}
        sequence = 0
        patch_path: list[ReleaseAsset] | None = None
        while queue:
            cost, hops, _, node, path = heapq.heappop(queue)
            if node == target:
                patch_path = path
                break
            if best.get(node) != (cost, hops):
                continue
            for asset in eligible_edges.get(node, []):
                next_node = str(SemVer.parse(asset.to_version or ""))
                next_cost = cost + max(0, asset.size)
                next_hops = hops + 1
                if (next_cost, next_hops) >= best.get(next_node, (2**63 - 1, 2**31 - 1)):
                    continue
                best[next_node] = (next_cost, next_hops)
                sequence += 1
                heapq.heappush(queue, (next_cost, next_hops, sequence, next_node, path + [asset]))

        if patch_path:
            self._download_assets = patch_path
        else:
            full = next((asset for asset in self._candidate.assets if asset.kind == "full"), None)
            self._download_assets = [full] if full else []
        self._asset = self._download_assets[0] if self._download_assets else None
        for asset in self._download_assets:
            self._set_asset_space_requirement(asset)
        if len(self._download_assets) > 1:
            self._asset.required_bytes = sum(asset.required_bytes for asset in self._download_assets)

    def _verify_candidate_manifest(self) -> None:
        """Verify a release manifest when one is published.

        Older releases predate the updater and intentionally have no manifest;
        those remain usable through the complete ZIP fallback.  Once a public
        key is provisioned, signed manifests become mandatory.
        """

        candidate = self._candidate
        public_key = _configured_public_key()
        if not candidate:
            return
        if not candidate.manifest_url:
            if public_key:
                raise ValueError("Signed update manifest is missing from the release")
            return
        try:
            response = self._session.get(candidate.manifest_url, headers={"User-Agent": "MapleClassicReporter-Updater"}, timeout=(8, 20))
            response.raise_for_status()
            manifest = response.json()
            if not isinstance(manifest, dict) or str(manifest.get("version")) != candidate.version:
                raise ValueError("Update manifest version does not match the release")
            if public_key:
                if not candidate.signature_url:
                    raise ValueError("Signed update manifest is missing its signature")
                signature_response = self._session.get(candidate.signature_url, headers={"User-Agent": "MapleClassicReporter-Updater"}, timeout=(8, 20))
                signature_response.raise_for_status()
                if not verify_ed25519(canonical_json(manifest), signature_response.text.strip(), public_key):
                    raise ValueError("Update manifest signature is invalid")
            self._merge_manifest_assets(manifest)
        except Exception as error:
            if _configured_public_key():
                raise
            LOGGER.warning("Unable to verify optional update manifest: %s", error)

    def _merge_manifest_assets(self, manifest: dict[str, Any]) -> None:
        candidate = self._candidate
        if not candidate:
            return
        for item in list(manifest.get("patches", [])) + [manifest.get("full")]:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "")
            asset = next((value for value in candidate.assets if value.name == name), None)
            if asset:
                asset.digest = asset.digest or str(item.get("sha256") or "")
                asset.required_bytes = int(item.get("required_bytes") or asset.required_bytes)

    def _maybe_auto_download(self) -> None:
        config = self._get_config() or {}
        if bool(config.get("auto_update_enabled", True)) and self._asset:
            self.start_download()

    def start_download(self) -> bool:
        with self._lock:
            if not self._download_assets or not self._candidate:
                return False
            if self._download_thread and self._download_thread.is_alive():
                return False
            available = shutil.disk_usage(self._update_dir).free
            required = sum(max(0, asset.required_bytes) for asset in self._download_assets)
            if required and available < required:
                self._set_status(
                    UpdateState.INSUFFICIENT_SPACE,
                    required_bytes=required,
                    available_bytes=available,
                    error_code="insufficient_space",
                    error_message=f"需要 {required:,} bytes，目前可用 {available:,} bytes",
                )
                return False
            self._cancel.clear()
            self._download_thread = threading.Thread(target=self._download_worker, daemon=True, name="update-download")
            self._download_thread.start()
            return True

    def cancel_download(self) -> bool:
        self._cancel.set()
        return True

    def _download_worker(self) -> None:
        assets = list(self._download_assets)
        candidate = self._candidate
        if not assets or not candidate:
            return
        try:
            self._download_assets_loop(assets, candidate)
        except Exception as error:
            if any(asset.kind == "delta" for asset in assets):
                full = next((asset for asset in candidate.assets if asset.kind == "full"), None)
                if full and not self._cancel.is_set():
                    LOGGER.warning("Delta update download failed (%s), falling back to full package", error)
                    try:
                        self._set_asset_space_requirement(full)
                        self._download_assets = [full]
                        self._asset = full
                        self._download_assets_loop([full], candidate)
                        return
                    except Exception as full_error:
                        error = full_error
            LOGGER.warning("Update download failed: %s", error)
            self._set_status(UpdateState.ERROR, error_code="download_failed", error_message=str(error))

    def _download_assets_loop(self, assets: list[ReleaseAsset], candidate: ReleaseCandidate) -> None:
        total = sum(max(0, asset.size) for asset in assets)
        downloaded_total = 0
        package_paths: list[Path] = []
        for asset in assets:
            filename = asset.name
            partial = self._update_dir / f"{filename}.part"
            destination = self._update_dir / filename
            downloaded = partial.stat().st_size if partial.exists() else 0
            headers = {"User-Agent": "MapleClassicReporter-Updater", "Accept": "application/octet-stream"}
            if downloaded:
                headers["Range"] = f"bytes={downloaded}-"
            response = self._session.get(asset.url, headers=headers, stream=True, timeout=(10, 60))
            if downloaded and response.status_code == 416:
                partial.unlink(missing_ok=True)
                downloaded = 0
                response = self._session.get(asset.url, headers={"User-Agent": headers["User-Agent"]}, stream=True, timeout=(10, 60))
            response.raise_for_status()
            if downloaded and response.status_code != 206:
                partial.unlink(missing_ok=True)
                downloaded = 0
            response_total = int(response.headers.get("Content-Length") or 0) + downloaded
            total = max(total, downloaded_total + (response_total or asset.size))
            self._set_status(UpdateState.DOWNLOADING, downloaded_bytes=downloaded_total + downloaded, total_bytes=total, progress_percent=int((downloaded_total + downloaded) * 100 / max(1, total)))
            mode = "ab" if downloaded else "wb"
            with partial.open(mode) as output:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if self._cancel.is_set():
                        self._set_status(UpdateState.AVAILABLE, downloaded_bytes=downloaded_total + downloaded, total_bytes=total)
                        return
                    if not chunk:
                        continue
                    output.write(chunk)
                    downloaded += len(chunk)
                    self._set_status(UpdateState.DOWNLOADING, downloaded_bytes=downloaded_total + downloaded, total_bytes=total, progress_percent=int((downloaded_total + downloaded) * 100 / max(1, total)))
            output_hash = sha256_file(partial)
            if asset.digest and output_hash.lower() != asset.digest.lower():
                raise ValueError(f"Downloaded update SHA-256 does not match {asset.name}")
            os.replace(partial, destination)
            package_paths.append(destination)
            downloaded_total += downloaded

        if len(package_paths) > 1:
            self._package_path = self._compose_delta_chain(package_paths, candidate.version)
            for path in package_paths:
                path.unlink(missing_ok=True)
        else:
            self._package_path = package_paths[0]
        _write_pending_update(self._update_dir, self._package_path, candidate.version)
        self._set_status(UpdateState.READY, downloaded_bytes=downloaded_total, total_bytes=total, progress_percent=100, package_kind="delta" if all(asset.kind == "delta" for asset in assets) else assets[0].kind, error_code=None, error_message=None)

    def _compose_delta_chain(self, package_paths: list[Path], target_version: str) -> Path:
        """Merge sequential file-level patches into one final patch archive."""

        file_payloads: dict[str, bytes] = {}
        deleted: set[str] = set()
        final_target_files: dict[str, str] = {}
        first_version = ""
        for package_path in package_paths:
            with zipfile.ZipFile(package_path) as archive:
                metadata = json.loads(archive.read("patch.json"))
                if metadata.get("kind") != "delta":
                    raise ValueError("A multi-version update chain can only contain delta packages")
                first_version = first_version or str(metadata.get("from_version") or "")
                for relative in metadata.get("delete", []):
                    safe = safe_relative_path(relative)
                    file_payloads.pop(safe, None)
                    deleted.add(safe)
                for relative in metadata.get("files", {}):
                    safe = safe_relative_path(relative)
                    file_payloads[safe] = archive.read(f"files/{safe}")
                    deleted.discard(safe)
                target_files = metadata.get("target_files", {})
                if isinstance(target_files, dict):
                    final_target_files = {safe_relative_path(path): str(digest) for path, digest in target_files.items()}

        name = f"MapleClassicReporter-chain-to-v{target_version}-windows-x64.patch.zip"
        destination = self._update_dir / name
        patch = {
            "schema": 1,
            "kind": "delta",
            "from_version": first_version,
            "to_version": target_version,
            "files": {path: hashlib.sha256(payload).hexdigest() for path, payload in file_payloads.items()},
            "delete": sorted(deleted),
            "target_files": final_target_files,
        }
        with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            archive.writestr("patch.json", json.dumps(patch, ensure_ascii=False, sort_keys=True, indent=2))
            for relative, payload in file_payloads.items():
                archive.writestr(f"files/{relative}", payload)
        return destination

    def restart_and_apply(self) -> bool:
        with self._lock:
            if not self._apply_enabled:
                self._set_status(UpdateState.ERROR, error_code="source_mode", error_message="更新套用只在 Windows 發行版中啟用")
                return False
            if self._status.get("state") != UpdateState.READY.value or not self._package_path or not self._candidate:
                return False
            if self._is_busy():
                self._set_status(UpdateState.WAITING_FOR_IDLE)
                if not self._apply_thread or not self._apply_thread.is_alive():
                    self._apply_thread = threading.Thread(target=self._wait_then_apply, daemon=True, name="update-apply-wait")
                    self._apply_thread.start()
                return True
            return self._launch_updater_locked()

    def _wait_then_apply(self) -> None:
        while not self._cancel.is_set() and self._is_busy():
            time.sleep(0.5)
        if not self._cancel.is_set():
            with self._lock:
                self._launch_updater_locked()

    def _launch_updater_locked(self) -> bool:
        assert self._package_path and self._candidate
        helper = self._install_dir / "MapleClassicReporterUpdater.exe"
        if helper.is_file():
            helper_copy = self._update_dir / f"MapleClassicReporterUpdater-{self._candidate.version}.exe"
            shutil.copy2(helper, helper_copy)
            command = [str(helper_copy)]
            helper_cwd = self._update_dir
        else:
            if getattr(sys, "frozen", False):
                self._set_status(UpdateState.ERROR, error_code="missing_updater", error_message="發行資料夾缺少內建 updater")
                return False
            command = [sys.executable, "-m", "maple_reporter.update.updater_main"]
            helper_cwd = Path(__file__).resolve().parents[3]
        command.extend(
            [
                "--package",
                str(self._package_path),
                "--install-dir",
                str(self._install_dir),
                "--update-dir",
                str(self._update_dir),
                "--pid",
                str(os.getpid()),
                "--target-version",
                self._candidate.version,
            ]
        )
        try:
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            _write_pending_update(self._update_dir, self._package_path, self._candidate.version)
            subprocess.Popen(command, cwd=str(helper_cwd), creationflags=flags, close_fds=True)
            self._set_status(UpdateState.APPLYING)
            if self._close_app:
                self._close_app()
            return True
        except Exception as error:
            (self._update_dir / "pending-update.json").unlink(missing_ok=True)
            self._set_status(UpdateState.ERROR, error_code="launch_failed", error_message=str(error))
            return False

    def shutdown(self) -> None:
        self._cancel.set()
        for thread in (self._check_thread, self._download_thread):
            if thread and thread.is_alive():
                thread.join(timeout=0.2)


def _write_pending_update(update_dir: Path, package: Path, target_version: str) -> None:
    (update_dir).mkdir(parents=True, exist_ok=True)
    (update_dir / "pending-update.json").write_text(
        json.dumps({"package": str(package), "target_version": target_version, "created_at": _now()}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
