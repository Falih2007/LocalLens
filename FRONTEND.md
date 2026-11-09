# Frontend development and integration

## What changed

The user approved a frontend-only migration from vanilla HTML/CSS/JavaScript to React + TypeScript + Vite. The source lives in `frontend/`. Official shadcn/ui was initialized with **Base UI / Nova / neutral / Lucide / Geist**, using Tailwind v4 and `@/` aliases. Common requested primitives are committed as source under `src/components/ui/`.

The existing vanilla `ui/` files and their regression test remain as a fallback. Python inference, automatic scan selection, downloads, cleanup, schemas and `/api/*` contracts are preserved. The only Python change is static delivery: prefer the built frontend when present, serve checked local JS/CSS/font assets, inject the same per-launch token, and permit inline styles needed for component positioning. Script policy, host checks and API authentication remain unchanged. Encoded traversal outside the asset directory is rejected.

## Run the app

Double-click `Start-LocalLens.cmd` as before. The deliverable includes `frontend/dist`, so Node.js and npm are not needed for normal use. If that build is absent, Python serves the original UI. To deliberately use it, set `LOCALLENS_LEGACY_UI=1` before starting Python.

## Develop the frontend

Use Node.js 22.12+ (tested with 24.13.0) and npm. From `frontend/`:

```
npm ci
npm run build
npm test
```

For live development, first start the Python backend with `python app.py --no-window` from the project root. Set `LOCALLENS_API_URL` to the localhost URL it prints, then run `npm run dev` from `frontend/`. In PowerShell:

```
$env:LOCALLENS_API_URL='http://127.0.0.1:YOUR_PRINTED_PORT'
npm run dev
```

The Vite development plugin obtains the real session token from the backend HTML; the `/api` proxy preserves the backend's exact Host requirement. No API routes were added for the frontend migration. Development requires LOCALLENS_API_URL for the current launch; there is no fixed port fallback. Production uses the same origin automatically.

After changes, rebuild `frontend/dist` before sharing or using the normal launcher. The build splits secondary pages into separate chunks. Fonts are bundled locally; there are no font CDN requests.

## Design and instructions

Read `DESIGN.md` and `AGENTS.md`. Components use semantic colors and common tokens in `src/index.css`. Official primitives are source-owned and reusable; inspect upstream diffs before replacing local changes. Generated CLI imports referring to a bare `cn` were corrected to the configured `@/lib/utils` alias.

## shadcn MCP and skill

The official `shadcn-ui/ui` skill at `skills/shadcn` was installed using Codex's skill installer, under the user's Codex skills directory. It is available to subsequent sessions/turns.

One shadcn MCP entry was added to the user's existing Codex settings, with a backup saved beside that settings file. It uses the official `npx -y shadcn@latest mcp` command through Windows `cmd /c`. Its cwd points at this project's `frontend/` so registries and aliases resolve correctly. If you move the project or use this MCP entry for a different project, update that cwd.

Direct validation succeeded: initialization, tools/list and a read-only official registry search. Tools include registry discovery, item listing, search, inspection, examples, add commands and audit checklist. **Restart Codex to load the new MCP entry into its own tool list.** The direct process test does not prove the current already-running chat has reloaded that configuration. No restart was performed automatically.

No private Codex configuration or credentials are included in this source archive. The configuration is machine-local; the app itself does not require MCP or the skill to run.

## Verification boundaries

Frontend tests use actual saved-result fixtures kept separately from the live journal. They verify manual/automatic result merging, filter behavior, evidence selection, quick/broader start and stop controls, original manual payloads, NPU unavailable states, theme persistence, form drafts across navigation, and the real evidence dialog. Backend tests check compiled asset serving, token injection and traversal rejection in addition to the existing inference/cleanup tests. No new multi-GB model download is required for a frontend refactor.

In PowerShell, quote registry names beginning with @, for example `npx shadcn@latest search '@shadcn' -q sidebar`, to avoid splatting syntax. Local primitive changes include routing cn imports through the shared alias and rendering CardTitle as a semantic h2.

## Connect Devices addition

The new lazy-loaded Connect Devices page uses the existing Sidebar, Card, Dialog, Field, Alert, Empty and Table primitives. Additive /api/connect endpoints provide discovery, approval status, connection tests, source companion download and experimental inference. Existing single-device API shapes and test protocols are preserved. See CONNECT-DEVICES.md and DISTRIBUTED-RESEARCH.md for setup and validation boundaries.
