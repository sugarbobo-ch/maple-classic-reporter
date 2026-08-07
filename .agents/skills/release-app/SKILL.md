---
name: release-app
description: Automatically run unit tests, bump version, build standalone Windows executable, git commit, tag, push to GitHub, and trigger release workflow.
---

# Release App Skill

Use this skill when the user requests to release a new version, create a release tag, or run `commit push release` (or `/release-app`).

## Execution Steps

1. **Execute Release Script**:
   Run the project's automated release tool in non-interactive mode:
   ```bash
   .venv\Scripts\python.exe scripts/release.py --yes
   ```
   If the user specifies a version or release type (e.g. `minor`, `patch`, `major`, or `v1.1.0`), pass the corresponding flag:
   ```bash
   .venv\Scripts\python.exe scripts/release.py --type minor
   ```

2. **Monitor GitHub Actions CI/CD**:
   After the script pushes the Git commit and release tag (e.g. `v1.0.0`), check the status of the triggered GitHub Actions workflow:
   ```bash
   gh run list --limit 3
   ```
   Wait for the workflow to complete using:
   ```bash
   gh run watch
   ```

3. **Verify & Report**:
   Ensure the GitHub Release and ZIP package are created and published cleanly, then report the release URL and summary to the user.
