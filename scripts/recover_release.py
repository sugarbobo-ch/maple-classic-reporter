"""Publish a verified existing CI bundle, uploading assets sequentially."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
from urllib.parse import urlencode, urlparse


def run(*args: str) -> str:
    return subprocess.check_output(args, text=True, encoding="utf-8").strip()


def api(repo: str, path: str):
    return json.loads(run("gh", "api", f"repos/{repo}/{path}"))


def release_for_tag(repo: str, tag: str):
    releases = api(repo, "releases?per_page=100")
    matches = [release for release in releases if release["tag_name"] == tag]
    if len(matches) != 1 or not matches[0]["draft"]:
        raise RuntimeError("Recovery requires exactly one unpublished release draft")
    return matches[0]


def verify_files(directory: Path) -> dict[str, Path]:
    files = {}
    for file in directory.rglob("*"):
        if file.is_file():
            if file.name in files:
                raise RuntimeError(f"Duplicate artifact filename: {file.name}")
            files[file.name] = file
    for line in files["SHA256SUMS.txt"].read_text(encoding="utf-8").splitlines():
        digest, name = line.split(maxsplit=1)
        if Path(name).name != name or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise RuntimeError("Invalid checksum entry")
        with files[name].open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        if actual != digest:
            raise RuntimeError(f"Checksum mismatch: {name}")
    print(f"Verified {len(files)} CI assets", flush=True)
    return files


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--directory", type=Path, default=Path("dist/recovery"))
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if not re.fullmatch(r"v\d+\.\d+\.\d+", args.tag) or not args.run_id.isdigit():
        raise RuntimeError("Invalid release tag or CI run ID")
    repo = os.environ.get("GITHUB_REPOSITORY", "sugarbobo-ch/maple-classic-reporter")
    commit = run("git", "rev-list", "-n", "1", args.tag)
    ci_run = api(repo, f"actions/runs/{args.run_id}")
    if ci_run["head_sha"] != commit:
        raise RuntimeError("CI source does not match the release tag")
    if not args.directory.exists():
        subprocess.run([
            "gh", "run", "download", args.run_id, "--repo", repo,
            "--name", "MapleClassicReporter-windows-x64", "--dir", str(args.directory),
        ], check=True)
    files = verify_files(args.directory)
    full_name = f"MapleClassicReporter-{args.tag}-windows-x64.zip"
    required = {
        full_name, "SHA256SUMS.txt", "update-manifest-v1.json",
        "update-manifest-v1.json.sig", "bundle-manifest-v1.json",
        "bundle-manifest-v1.json.sig",
    }
    if not required <= files.keys():
        raise RuntimeError("CI artifact is missing required Windows release assets")
    if args.verify_only:
        return
    token = os.environ["GH_TOKEN"]
    for name in sorted(files, key=lambda name: (name != full_name, name)):
        file = files[name]
        with file.open("rb") as stream:
            digest = "sha256:" + hashlib.file_digest(stream, "sha256").hexdigest()
        for attempt in range(3):
            release = release_for_tag(repo, args.tag)
            existing = next((asset for asset in release["assets"] if asset["name"] == name), None)
            if existing:
                if existing["state"] == "uploaded" and existing.get("digest") == digest:
                    print(f"Verified existing asset: {name}", flush=True)
                    break
                if existing["state"] == "uploaded":
                    raise RuntimeError(f"Existing asset differs from CI: {name}")
                # A failed request may leave an incomplete asset on this draft.
                subprocess.run(["gh", "api", "--method", "DELETE",
                                f"repos/{repo}/releases/assets/{existing['id']}"], check=True)
            upload_url = release["upload_url"].split("{")[0]
            if urlparse(upload_url).netloc != "uploads.github.com":
                raise RuntimeError("Unexpected GitHub upload host")
            print(f"Uploading {name}, attempt {attempt + 1}/3", flush=True)
            result = subprocess.run([
                "curl", "--config", "-", "--http1.1", "--request", "POST",
                "--upload-file", str(file), "--header", "Content-Type: application/octet-stream",
                "--connect-timeout", "20", "--max-time", "600", "--fail-with-body",
                upload_url + "?" + urlencode({"name": name}),
            ], input=f'header = "Authorization: Bearer {token}"\n', text=True,
                stdout=subprocess.PIPE)
            if result.returncode == 0:
                asset = json.loads(result.stdout)
                if asset.get("digest") != digest or asset["size"] != file.stat().st_size:
                    raise RuntimeError(f"Uploaded asset verification failed: {name}")
                break
            print(f"Upload failed with curl exit code {result.returncode}: {result.stdout[:500]}", flush=True)
            if attempt == 2:
                raise RuntimeError(f"Upload retries exhausted: {name}")
            time.sleep(10)
    release = release_for_tag(repo, args.tag)
    assets = {asset["name"]: asset for asset in release["assets"]}
    for name, file in files.items():
        with file.open("rb") as stream:
            digest = "sha256:" + hashlib.file_digest(stream, "sha256").hexdigest()
        if assets[name]["state"] != "uploaded" or assets[name].get("digest") != digest:
            raise RuntimeError(f"Final asset verification failed: {name}")
    subprocess.run(["gh", "release", "edit", args.tag, "--repo", repo,
                    "--draft=false", "--latest"], check=True)
    print(f"Published {args.tag}", flush=True)


if __name__ == "__main__":
    main()
