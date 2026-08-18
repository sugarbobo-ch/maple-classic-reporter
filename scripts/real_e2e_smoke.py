#!/usr/bin/env python3
"""Explicit real-service smoke checks.

These checks are intentionally opt-in. They use real third-party accounts and
may create a Drive file, send a Discord message, or submit a SurveyCake report.
They never run as part of the normal unit-test suite.
"""

from __future__ import annotations

import argparse
import os
import tempfile
from pathlib import Path

from maple_reporter.automation.form_filler import submit_gamania_report
from maple_reporter.discord.webhook_service import upload_evidence_to_discord
from maple_reporter.gdrive.drive_service import GoogleDriveManager
from maple_reporter.utils.urls import is_safe_https_url


class SmokeConfigurationError(RuntimeError):
    pass


def _env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SmokeConfigurationError(f"Missing required environment variable: {name}")
    return value


def _require_gate() -> None:
    if os.environ.get("MAPLE_REPORTER_REAL_E2E") != "1":
        raise SmokeConfigurationError(
            "Set MAPLE_REPORTER_REAL_E2E=1 to enable real-service smoke checks."
        )


def _make_evidence_file(temp_dir: Path) -> Path:
    evidence_path = temp_dir / "maple-reporter-real-e2e.mp4"
    # The upload services only need a small local file. The production recorder
    # is deliberately not touched by this smoke check.
    evidence_path.write_bytes(b"maple-classic-reporter real e2e smoke fixture\n")
    return evidence_path


def run_gdrive(args: argparse.Namespace, evidence_path: Path) -> str:
    client_config = os.environ.get(
        "MAPLE_REPORTER_E2E_OAUTH_CLIENT",
        str(Path("build_secrets") / "google_oauth_client.json"),
    )
    token_path = os.environ.get("MAPLE_REPORTER_E2E_TOKEN_PATH")
    manager = GoogleDriveManager(token_path=token_path)

    if not manager.is_authenticated():
        if not args.allow_oauth:
            raise SmokeConfigurationError(
                "Drive is not authenticated. Re-run with --allow-oauth for an interactive OAuth flow."
            )
        ok, message = manager.authenticate_interactive(client_config)
        if not ok:
            raise RuntimeError(f"Google OAuth failed: {message}")

    if not manager.is_authenticated():
        raise RuntimeError("Google Drive still reports unauthorised after OAuth.")

    folder = os.environ.get("MAPLE_REPORTER_E2E_DRIVE_FOLDER", "MapleClassicReporter_E2E")
    ok, result = manager.upload_file_and_make_public(str(evidence_path), folder)
    if not ok or not is_safe_https_url(result):
        raise RuntimeError(f"Google Drive upload failed or returned an unsafe URL: {result}")
    print(f"Google Drive: uploaded test evidence to {result}")
    return result


def run_discord(evidence_path: Path) -> str:
    webhook = _env("MAPLE_REPORTER_E2E_DISCORD_WEBHOOK")
    ok, result = upload_evidence_to_discord(
        webhook,
        str(evidence_path),
        "Maple Classic Reporter real E2E smoke test",
    )
    if not ok or not is_safe_https_url(result):
        raise RuntimeError(f"Discord upload failed or returned an unsafe URL: {result}")
    print(f"Discord: uploaded test evidence to {result}")
    return result


def run_surveycake(args: argparse.Namespace, evidence_url: str | None) -> None:
    if not args.allow_submit:
        raise SmokeConfigurationError(
            "SurveyCake submission is disabled by default. Re-run with --allow-submit."
        )
    evidence = evidence_url or _env("MAPLE_REPORTER_E2E_EVIDENCE_URL")
    if not is_safe_https_url(evidence):
        raise SmokeConfigurationError("MAPLE_REPORTER_E2E_EVIDENCE_URL must be a safe HTTPS URL.")

    ok, message = submit_gamania_report(
        suspect_id=_env("MAPLE_REPORTER_E2E_SUSPECT_ID"),
        server_name=os.environ.get("MAPLE_REPORTER_E2E_SERVER", "Gamania"),
        map_name=_env("MAPLE_REPORTER_E2E_MAP"),
        note=os.environ.get("MAPLE_REPORTER_E2E_NOTE", "Maple Reporter real E2E smoke test"),
        evidence_url=evidence,
        headless=args.headless,
    )
    if not ok:
        raise RuntimeError(f"SurveyCake submission was not confirmed: {message}")
    print(f"SurveyCake: confirmed submission ({message})")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("service", choices=("gdrive", "discord", "surveycake"))
    parser.add_argument(
        "--allow-oauth",
        action="store_true",
        help="Allow an interactive Google OAuth flow if no valid token exists.",
    )
    parser.add_argument(
        "--allow-submit",
        action="store_true",
        help="Allow the irreversible SurveyCake submission step.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run the SurveyCake browser headlessly.",
    )
    args = parser.parse_args()

    _require_gate()
    with tempfile.TemporaryDirectory(prefix="maple-reporter-real-e2e-") as temp_dir:
        evidence_path = _make_evidence_file(Path(temp_dir))
        if args.service == "gdrive":
            run_gdrive(args, evidence_path)
        elif args.service == "discord":
            run_discord(evidence_path)
        else:
            run_surveycake(args, None)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (SmokeConfigurationError, RuntimeError) as error:
        raise SystemExit(f"REAL E2E NOT RUN: {error}")
