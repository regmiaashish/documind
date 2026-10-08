# DocuMind frontend

Use the [frontend testing walkthrough](WALKTHROUGH.md) to check uploads, cited answers,
user isolation, orders, ticket confirmation, rate limits, and recovery step by step.

React + TypeScript, built with Vite. Compose serves the static build through Nginx
at http://localhost:3000 and proxies `/api/` to the backend. No frontend `.env` is needed.

For local development, keep the API running on port 8000 and run from the repo root:

```bash
make dev-web
```

Open the Vite address printed in the terminal. Node 22 is recommended.

```bash
make build-web
make test-web
```

See the [root README](../README.md) for setup and the [Phase 4 review](../docs/PHASE_4.md)
for the components, behavior, and verification limits.
