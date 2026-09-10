# Project instructions

Read and follow `~/.codex/RTK.md` before running shell commands.

## Interface consistency

- Use the existing component library, design tokens, and Lucide icon family for application UI.
- Separate adjacent labels, counts, and statuses with layout spacing, separate text elements, or explanatory wording. Do not use decorative dot separators such as `·`, `•`, or `・`.
- Do not use emoji or Unicode symbol glyphs as interface icons, including native text triangles and arrows. Use named Lucide icons for expand/collapse, navigation, playback, and status controls authored by the application. Replace native disclosure markers when creating application accordions.
- These restrictions apply to application-authored UI, not player names, user-entered evidence descriptions, or browser/OS-owned controls.
- For closely nested rounded surfaces, derive the outer radius from the inner radius plus inset. Reuse project radius and spacing tokens.
- When changing interface text or controls, inspect modified components for decorative separators, emoji, and text-based icons before finishing.
