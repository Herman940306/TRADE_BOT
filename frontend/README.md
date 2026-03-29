# Sovereign Command Hub - Frontend

React 18 + TypeScript + Vite 5 + Tailwind CSS 3 dashboard for Project Autonomous Alpha.

## Development

```bash
cd frontend
npm install
npm run dev
```

The dev server proxies `/api` and `/ws` requests to `http://localhost:8000` (the FastAPI backend).

## Environment

Set your API token in localStorage:

```js
localStorage.setItem('sovereign_token', '<your-token>');
```

The token must match the `FRONTEND_API_TOKEN` environment variable on the backend.

## Build

```bash
npm run build
```

Output goes to `frontend/dist/` for static serving or Docker inclusion.
