# LocalLens agent instructions

## Frontend
- Primary design system: official shadcn/ui, Base UI primitives, Nova style. Source lives in `frontend/src`; production assets live in `frontend/dist`.
- Use Tailwind v4 semantic tokens from `frontend/src/index.css`. Do not mix in a second UI kit or CSS-in-JS system.
- Consult `docs/DESIGN.md` and the installed official shadcn skill before component work. Read `components.json`; use the configured aliases and Base UI `render` APIs, not Radix `asChild` APIs.
- Prefer existing official components/blocks. Use shadcn MCP registry discovery where appropriate; otherwise use the official CLI from `frontend/`. Search the explicitly requested official @shadcn registry, read component docs, and inspect generated files.
- Check installed components before adding more. Fix generated utility imports to `@/lib/utils`; keep component imports through that shared alias. The generated utility re-exports the official `cn` package.
- Shared primitives belong in `src/components/ui`; application compositions in `src/components`; pages in `src/pages`; API/types/formatting in `src/lib`.
- Use FieldGroup/Field for forms, explicit input labels, semantic headings, accessible dialog titles, keyboard navigation and visible focus. Preserve light, dark, system theme and reduced-motion behavior.
- Keep desktop and narrow layouts usable. Horizontal overflow belongs inside tables and evidence panels, never on the page.
- Use consistent Geist typography, 4px spacing steps, modest radii, neutral colors, subtle borders and restrained motion. Avoid decorative gradients and fake visual data.
- Preserve API behavior and all existing workflows: one-click scans, cancellation, manual tests, hardware refresh, OpenVINO capability checks, journal filtering, evidence inspection and JSON export.
- The journal must include BOTH automatic prompt-test attempts and manual llama-bench records, newest first, with explicit method labels. Temporary model deletion must never remove saved evidence.
- Do not add dependencies without a concrete need. Use the npm lockfile and `npm ci` for reproducible installs.

## Backend and evidence
- Preserve Python benchmark/adapter behavior and `/api/*` contracts. A frontend refactor is not permission to change inference protocols, comfort thresholds, download/cleanup rules or schemas.
- Never fabricate measurements, imply an untested model was tested, or convert an estimate into a measured score. NPU execution remains unimplemented until a real adapter is built and verified.
- Keep local-session token and exact localhost Host validation. Production static delivery changes must retain path traversal checks and local-only binding.
- Do not delete or modify installed user models. Clean up only app-owned scratch; preserve reports and logs.

## Verification
- In `frontend/`: run `npm run build` and `npm test` after relevant UI changes.
- In the project root: run `python -m unittest discover -s tests -v` for backend/static integration changes and `node tests/test_journal.cjs` for legacy journal changes.
- Use real saved fixtures for result regressions. Fixture data must never populate a fresh live journal as fabricated measurements.
- Visually inspect rendered desktop/mobile and light/dark interfaces when tools permit. Report precisely what was checked; never claim screenshot verification without seeing it.
- Build production assets before packaging. Exclude node_modules, caches, private Codex settings and development scratch from deliverables.

## Connect Devices prototype

The primary frontend now includes Connect Devices. Read CONNECT-DEVICES.md for companion/build setup and docs/DISTRIBUTED-RESEARCH.md for compatibility, security and milestone status. cluster.py, connectnet.py, companion.py and distributed.py add separate authenticated LAN transport and experimental inference workflows. Existing single-device protocols and recommendations are unchanged. Never equate discovery, pairing or a transport fixture with proven shared-model inference. Phone hardware testing remains pending; all virtual RAM is excluded from physical capacity. Run the complete Python and frontend suites after changes. Do not package runtime reports, keys or pairing credentials.
