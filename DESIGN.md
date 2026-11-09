# LocalLens design system

## Direction
A quiet, practical local-AI workspace inspired by Apple's typography and Linear's clear hierarchy. Neutral surfaces, deliberate whitespace, concise labels, minimal decoration. Data and actions lead; hardware illustrations and ornamental gradients are omitted.

## Implementation
React + TypeScript + Vite. Tailwind v4. Official shadcn/ui `base-nova`, Base UI primitives, Lucide icons. npm is the package manager; the lockfile pins the resolved toolchain. The existing Python API remains the source of truth. The vanilla UI under `ui/` is retained as a fallback.

## Foundations
- **Font:** locally bundled Geist Variable, with system sans-serif fallback. No remote font requests.
- **Typography:** page headings 30–36px / semibold; metric figures 24–30px / medium with tabular numerals; body 14px; supporting text 12px; restrained 10px uppercase section labels.
- **Spacing:** 4px base steps. Page padding 16px mobile / 32px desktop; 24px between major sections; 16px between related cards and controls.
- **Geometry:** base radius 8px; component variants derive their radii from the common token. Compact 32–36px controls. Hairline borders/rings, minimal elevation.
- **Colors:** official neutral OKLCH roles: background, foreground, card, muted, accent, border, primary, destructive. No arbitrary per-page accents. Status meaning is always carried by text and badges, not color alone.
- **Themes:** Light / Dark / System via the appearance menu. Persisted locally; system changes are observed. Components inherit semantic tokens; no per-page dark color patches.
- **Motion:** brief opacity/position transitions in official components, and a restrained busy indicator. Respect prefers-reduced-motion.

## Components and conventions
- Navigation: official Sidebar, with icon collapse on desktop and its built-in Sheet on mobile. Hash routes retain overview / automatic / models / benchmark / history identifiers.
- Surfaces: full Card composition. Avoid nesting cards merely for decoration.
- Forms: FieldGroup, Field, FieldLabel, Input, Checkbox and ToggleGroup; native validation and explicit disabled/pending states.
- Data: Table for the advisor and journal; metrics for the recommendation; Badge for measured/estimated/method/state labels. Empty for no evidence; Skeleton for loading; Alert for errors and limitations.
- Overlays: controlled Dialog for saved evidence, with title, description, focus management and Escape close. DropdownMenu for theme choices. Tooltip for icon-only actions.
- Buttons: use official default/outline/ghost/destructive variants. Icons inside buttons use data-icon; icon-only buttons have accessible names.
- Custom application components: PageHeader, MetricCard, RecommendationCard, EvidenceDialog and shared empty/evidence actions.
- Class names primarily express layout. Primitive color/type/size recipes belong in the component variant or global tokens, not scattered overrides.

## Information architecture
1. Overview: detected hardware, latest measured recommendation, privacy/context notes.
2. Find my model: one-click setup, download budget, quick/broader choice, truthful progress, stop and cleanup, recommendation and backend comparison.
3. Model advisor: clearly marked RAM estimates; no invented speed.
4. Manual benchmark: existing file-path controls and CPU/GPU selection; separate optional NPU runtime capability check.
5. Results: one journal of automatic and manual measurements, newest first, method filters, raw evidence and unchanged JSON export shape.

## Trust and accessibility
Use “Measured” only for actual completed inference. Memory estimates remain estimates. Prompt-test decode throughput is not whole-request latency or answer quality. Distinguish test protocols and preserve every saved result after temporary-file cleanup. Unavailable/failed backends have explanatory text rather than zero scores.

One semantic main landmark; skip link; input labels; visible focus; modal titles; semantic tables; narrow-table scrolling; loading/status announcements; keyboard-operable navigation. Test both themes and desktop/mobile rendering.

## Scope
Only components needed by this application and the explicitly requested reusable set are installed; do not install every registry component or add a showcase page without a product need. No benchmark protocol or API changes are part of this design migration.

## Connect Devices prototype

The primary frontend now includes Connect Devices. Read CONNECT-DEVICES.md for companion/build setup and DISTRIBUTED-RESEARCH.md for compatibility, security and milestone status. cluster.py, connectnet.py, companion.py and distributed.py add separate authenticated LAN transport and experimental inference workflows. Existing single-device protocols and recommendations are unchanged. Never equate discovery, pairing or a transport fixture with proven shared-model inference. Phone hardware testing remains pending; all virtual RAM is excluded from physical capacity. Run the complete Python and frontend suites after changes. Do not package runtime reports, keys or pairing credentials.
