# Full-Stack Template

A minimal React + Vite, Express, and Sequelize starter you can download, customize, and **deploy for free on [Render](https://render.com)**. It uses SQLite locally (nothing to install) and PostgreSQL in production, picking the dialect automatically from a single environment variable.

## Stack

- **Frontend:** React 18 + Vite 5 (JavaScript/JSX)
- **Backend:** Node.js + Express (ES modules)
- **Database:** Sequelize ORM — **SQLite for local dev**, **PostgreSQL on Render**, selected at startup from `DATABASE_URL`
- **Deploy:** Render free tier (free web service + free Postgres) via `render.yaml` Blueprint
- **Docker:** used only by Render's build — local dev needs no Docker

## Project structure

```
.
├── backend/
│   ├── package.json
│   ├── server.js
│   └── db.js
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   └── src/
│       ├── main.jsx
│       ├── App.jsx
│       └── styles.css
├── Dockerfile
├── render.yaml
├── .env.example
├── .gitignore
├── .dockerignore
└── README.md
```

## Local development

No database to install — SQLite is built in. The backend creates a `data.sqlite` file on first run.

Open two terminals:

**Terminal 1 — backend**
```bash
cd backend
npm install
npm run dev
```

**Terminal 2 — frontend**
```bash
cd frontend
npm install
npm run dev
```

Then open **http://localhost:5173**. The Vite dev server proxies `/api` requests to the backend on port 3001.

## Deploy to Render

1. Push this repo to GitHub.
2. In Render, click **New → Blueprint** and connect your repo.
3. Render reads `render.yaml`, provisions a free Postgres database and a free Docker web service, and wires `DATABASE_URL` automatically — no connection string to copy/paste.

Notes on the free tier:
- The free web service **sleeps after inactivity**, so the first request after idle has a ~30s cold start.
- Render's **free Postgres expires after 30 days**.

## Endpoints

- `GET /api/health` — checks the database connection, returns `{ "status": "ok", "db": "sqlite" | "postgres" }`
- `GET /api/hello` — returns `{ "message": "Hello from the backend 👋" }`
- `GET *` (production only) — serves the built frontend
