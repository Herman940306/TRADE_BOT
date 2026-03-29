# Copilot Workspace Instructions

## Agent Plugin Usage Policy

- Always prefer installed MCP tools and marketplace agent plugins before writing custom ad-hoc implementations.
- For library, framework, SDK, API, CLI, or cloud-service documentation requests, always use Context7 tools.
- If the user provides a library ID (for example, /supabase/supabase), use it directly.
- If no library ID is provided, resolve the library first, then query docs.
- If a version is requested, include that version context in the Context7 query.

## Prompting Patterns

- Implement basic authentication with Supabase. use library /supabase/supabase for API and docs.
- How do I set up Next.js 14 middleware? use context7

## Reliability Guardrails

- Keep outputs professional and GitHub-ready.
- Do not use floating-point math for currency logic.
- Prefer deterministic, auditable steps with explicit assumptions.
