# Changelog

All notable changes to `polistress` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!--
Guidelines:
- Add a new entry under `## [Unreleased]` as you work — no batching up for release day.
- Group entries under: Added, Changed, Deprecated, Removed, Fixed, Security.
- Reference the spec slug and PR number:  "Added dark mode (spec: dark-mode, #42)".
- On release, rename `[Unreleased]` to the new version with the release date,
  and open a fresh `[Unreleased]` section at the top.
- The release-drafter workflow auto-populates draft release notes from PRs —
  keep PR titles tidy so they flow straight into here.
-->

## [Unreleased]

### Added
- Initial polistress engine (spec: polistress-grc-simulation-engine): four packages under `src/polistress` —
  `worldgraph` (typed NetworkX knowledge graph with SQLite persistence and neighbors/paths/domain queries),
  `personas` (persona synthesis with recency-weighted SQLite memory and seven archetypes),
  `simulation` (discrete tick loop, async Anthropic decisions with model tiering, append-only SQLite event log),
  and `report` (grounded findings register with framework mappings, CSV export, and event-cited Q&A)
- `scripts/generate_org.py` — deterministic synthetic org generator (~150 people, 8 teams, 40 assets, 25 controls, 10 findings, 5 policies)
- `scenarios/ai_usage_policy.yaml` — ready "AI Usage Policy rollout" scenario
- `polistress` typer CLI: `ingest`, `simulate`, `report`, `ask`
- `examples/` — example findings register reproducible without an API key
- pytest suite covering graph, persona synthesis, and event-log integrity (LLM mocked only in tests)
- Roles section in spec templates (`implementer`, `reviewer`, `qa`, `product_owner`) for per-spec responsibility assignment
- `roles.default_*` block in `.openspec/config.yaml` and `.openspec/defaults.yaml` for repo-wide default role assignments
- `scripts/openspec scaffold` now reads `roles.default_*` from config and pre-fills new specs
- Onboarding interview (`.openspec/onboarding.yaml`) prompts for default implementer / reviewer / qa / product_owner
- `Makefile` with convenience targets: `check`, `scaffold`, `scaffold-bug`, `test`, `status`, `setup`, `cleanup-template-specs`, `apply-branch-protection`
- `scripts/cleanup-template-specs` removes the template's internal design specs from a fresh fork
- `.vscode/settings.json` and `.vscode/extensions.json` with YAML schemas, markdownlint config, and recommended extensions
- `renovate.json.example` as an opt-in alternative to `dependabot.yml`
- Spec lifecycle state diagram in [`docs/OPENSPEC.md`](docs/OPENSPEC.md)
- **Enterprise hardening:**
  - `.github/workflows/license-scan.yml` + `.licenses/policy.yaml` — ScanCode-based OSS license enforcement
  - `.github/workflows/container-scan.yml` — Hadolint + Trivy scanning, auto-skips when no Dockerfile present
  - `.github/workflows/spec-metrics.yml` — weekly DORA-style report on spec status, role coverage, PR→spec link rate
  - `docs/branch-protection-ruleset.json` + `scripts/apply-branch-protection` — one-command branch protection bootstrap
  - `SECRETS.md` — secrets-management policy with rotation cadences and incident response
  - PR template extended with accessibility, privacy / data-handling, and security checklists
- `CONTRIBUTING.md` documents the `roles` block in the spec workflow
- `CLAUDE.md` Step 5 now instructs Claude to walk users through `roles` during scaffolding
- `CLAUDE.md` Step 6 now instructs Claude to clean up template-internal specs

### Changed
-

### Deprecated
-

### Removed
-

### Fixed
-

### Security
-

---

## [0.1.0] — YYYY-MM-DD

### Added
- Initial release.

[Unreleased]: https://github.com/arananet/polistress/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/arananet/polistress/releases/tag/v0.1.0
