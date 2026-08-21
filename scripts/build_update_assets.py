#!/usr/bin/env python3
"""Build signed bundle manifests and file-level portable update packages."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import zipfile
from pathlib import Path
from typing import Any

from maple_reporter.update.manifest import CURRENT_MANIFEST_SCHEMA, canonical_json, sha256_file, safe_relative_path


def iter_bundle_files(bundle: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for path in sorted(bundle.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(bundle).as_posix()
        safe_relative_path(relative)
        result[relative] = {"size": path.stat().st_size, "sha256": sha256_file(path)}
    return result


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sign_payload(payload: bytes, private_key: str | None) -> str | None:
    if not private_key:
        return None
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    key_bytes = base64.b64decode(private_key.encode("ascii"), validate=True)
    signature = Ed25519PrivateKey.from_private_bytes(key_bytes).sign(payload)
    return base64.b64encode(signature).decode("ascii")


def signed_json(path: Path, value: Any, private_key: str | None) -> None:
    write_json(path, value)
    signature = sign_payload(canonical_json(value), private_key)
    if signature:
        path.with_suffix(path.suffix + ".sig").write_text(signature + "\n", encoding="ascii")


def build_delta(previous_bundle: Path, current_bundle: Path, previous_version: str, version: str, output: Path) -> dict[str, Any]:
    previous = iter_bundle_files(previous_bundle)
    current = iter_bundle_files(current_bundle)
    changed = {path: info for path, info in current.items() if previous.get(path, {}).get("sha256") != info["sha256"]}
    deleted = sorted(set(previous) - set(current))
    patch = {
        "schema": CURRENT_MANIFEST_SCHEMA,
        "kind": "delta",
        "from_version": previous_version,
        "to_version": version,
        "files": {path: info["sha256"] for path, info in changed.items()},
        "delete": deleted,
        "target_files": {path: info["sha256"] for path, info in current.items()},
        "target_size": sum(info["size"] for info in current.values()),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        archive.writestr("patch.json", json.dumps(patch, ensure_ascii=False, sort_keys=True, indent=2))
        for relative in changed:
            archive.write(current_bundle / Path(relative), f"files/{relative}")
    patch["asset_size"] = output.stat().st_size
    patch["sha256"] = sha256_file(output)
    return patch


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--full-zip", type=Path, required=True)
    parser.add_argument("--previous-bundle", type=Path)
    parser.add_argument("--previous-version")
    parser.add_argument("--signing-key-env", default="UPDATE_SIGNING_KEY")
    args = parser.parse_args()

    bundle = args.bundle_dir.resolve()
    output = args.output_dir.resolve()
    if not (bundle / "MapleClassicReporter.exe").is_file():
        raise SystemExit(f"Bundle executable is missing: {bundle / 'MapleClassicReporter.exe'}")
    files = iter_bundle_files(bundle)
    bundle_manifest = {
        "schema": CURRENT_MANIFEST_SCHEMA,
        "platform": "windows-x64",
        "version": args.version,
        "bundle_root": "MapleClassicReporter",
        "total_size": sum(info["size"] for info in files.values()),
        "files": files,
    }
    private_key = os.environ.get(args.signing_key_env, "").strip() or None
    bundle_manifest_path = output / "bundle-manifest-v1.json"
    signed_json(bundle_manifest_path, bundle_manifest, private_key)

    # Keep a copy inside the full recovery ZIP so the standalone updater can
    # verify every extracted file without another network request.
    with zipfile.ZipFile(args.full_zip.resolve(), "a", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        if "bundle-manifest-v1.json" not in archive.namelist():
            archive.write(bundle_manifest_path, "bundle-manifest-v1.json")

    full_zip = args.full_zip.resolve()
    if not full_zip.is_file():
        raise SystemExit(f"Full release ZIP is missing: {full_zip}")
    full_asset = {
        "name": full_zip.name,
        "size": full_zip.stat().st_size,
        "sha256": sha256_file(full_zip),
        "required_bytes": full_zip.stat().st_size + bundle_manifest["total_size"] + 64 * 1024 * 1024,
    }
    patches: list[dict[str, Any]] = []
    if args.previous_bundle and args.previous_version:
        previous_bundle = args.previous_bundle.resolve()
        if previous_bundle.is_dir():
            patch_name = f"MapleClassicReporter-v{args.previous_version}-to-v{args.version}-windows-x64.patch.zip"
            patch = build_delta(
                previous_bundle,
                bundle,
                args.previous_version,
                args.version,
                output / patch_name,
            )
            patch.update({"name": patch_name, "required_bytes": patch["asset_size"] + max(1, bundle_manifest["total_size"] // 10) + 64 * 1024 * 1024})
            patches.append(patch)

    update_manifest = {
        "schema": CURRENT_MANIFEST_SCHEMA,
        "platform": "windows-x64",
        "version": args.version,
        "bundle_manifest": "bundle-manifest-v1.json",
        "full": full_asset,
        "patches": patches,
    }
    signed_json(output / "update-manifest-v1.json", update_manifest, private_key)
    print(json.dumps({"version": args.version, "files": len(files), "patches": len(patches)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
