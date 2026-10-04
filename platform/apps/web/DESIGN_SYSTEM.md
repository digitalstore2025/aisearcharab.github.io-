# Web Design System — Chapters 2–5

## Identity source

The Next.js workspace reuses the established AISearcharab identity rather than inventing a second brand: navy/deep navy, teal, secondary teal, and gold. The existing SVG mark is copied into `public/brand-mark.svg` and rendered through `next/image`.

## Typography

- Body: `IBM_Plex_Sans_Arabic` via `next/font/google`, weights 400–700.
- Headings: `Noto_Sans_Arabic` variable font via `next/font/google`.
- Both are self-hosted by Next.js after build-time retrieval; no browser request to Google Fonts is required.
- Arabic and Latin subsets are explicit.

## Accessibility and color

The legacy brand tokens remain the visual authority. Two text-specific corrections are introduced because the original muted and warning colors do not reach WCAG AA for normal text on white:

- `--muted-text: #6b7785` instead of using `#7b8794` for normal text.
- `--warning-text: #94611b` instead of using `#a66d1f` for normal text.

`scripts/audit_design.py` computes WCAG contrast ratios and fails below 4.5:1 for required text pairs.

## Layout and routing

A route group `(workspace)` supplies one shared workspace layout without changing public URLs. Current routes:

- `/dashboard`
- `/search`
- `/sources`
- `/research`
- `/projects`

The root `/` remains a public foundation page.

## Client boundary

All layouts and pages are Server Components by default. The only approved Client Component in this phase is `src/components/navigation/nav-links.tsx`, because active navigation requires `usePathname`. The Python structure audit fails if the client-module budget changes.

## Deferred intentionally

No API data fetching, authentication, Server Actions, RAG, agent tools, analytics tracking, or external network fetch is introduced in Chapters 2–5.
