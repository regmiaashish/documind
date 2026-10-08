# Phase 4 review: minimal frontend

The React/TypeScript frontend lives beside `backend/` and runs at localhost:3000
through Compose. It uses one page: a document sidebar, chat, and expandable sources.

| File | Responsibility |
| --- | --- |
| `src/App.tsx` | Selected demo user/document, uploads, document loading, and page layout |
| `src/components/Documents.tsx` | Upload control, document list, loading and retry states |
| `src/hooks/useChat.ts` | Independent question state, draft/final replacement, cancellation, retry |
| `src/components/Sources.tsx` | Fetch and expand an owner-scoped stored passage, with retry |
| `src/components/Icon.tsx` | Small inline SVG icons without an icon dependency |
| `src/lib/api.ts` | Same-origin HTTP requests; public local demo tokens only |
| `src/lib/sse.mjs` | Incremental UTF-8/SSE decoding and incomplete-stream detection |
| `src/types.ts` | Document, citation, answer, and UI message types |
| `src/styles.css` | Restrained colors, spacing, responsive layout, focus and reduced-motion styles |
| `vite.config.ts` | Local development proxy to the backend |
| `Dockerfile` / `nginx.conf` | Build static assets, serve them, and proxy API/SSE requests |

No state framework, CSS library, external font, frontend secret, or separate frontend
configuration is needed. React and React DOM are the only application dependencies.
TypeScript and Vite are build-time dependencies, excluded from the Nginx runtime.

The server remains stateless for chat. Browser messages disappear on reload or demo
user change. Changing users clears documents and chat; requests still require backend
permission checks. Markdown is displayed as plain text rather than executing HTML.

Uploads, document listing, questions, and source loading expose errors and retries.
A question snapshots its selected document and chunk size. Failed streaming clears
partial text. The page requires both a final answer and a terminal event to treat a
stream as complete. Users can press Enter to send or Shift+Enter for a newline.

## Verification

TypeScript checking and the production build pass. Four stream-decoder tests cover
fragmented UTF-8, CRLF framing, missing terminal/final events, and server errors.
Compose configuration validates. This workspace denies preview-server ports and
Docker access, so actual browser layout and live upload → streamed answer need the
README walkthrough on your machine. Check desktop and narrow/mobile widths, retry
states, source expansion, and switching to Bob.

Agent confirmation controls belong to Phase 5 and are not present yet.
