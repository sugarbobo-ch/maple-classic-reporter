"""Application update support for the portable Windows bundle."""

from maple_reporter.update.manifest import CURRENT_MANIFEST_SCHEMA, SemVer
from maple_reporter.update.service import UpdateService, UpdateState

__all__ = ["CURRENT_MANIFEST_SCHEMA", "SemVer", "UpdateService", "UpdateState"]
