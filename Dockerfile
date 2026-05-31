# syntax=docker/dockerfile:1
# Render-only multi-stage build. Local dev does not need Docker.

# Stage 1 — build the frontend (Node)
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# Stage 2 — Python runtime
FROM python:3.12-slim
ENV NODE_ENV=production
ENV PORT=3001
ENV PYTHONUNBUFFERED=1
WORKDIR /app/backend

# Copy backend source first so pip can find the app package, then install
COPY backend/ ./
RUN pip install --no-cache-dir .

# Copy built frontend into backend/public/ (served in production)
COPY --from=frontend-build /app/frontend/dist ./public

EXPOSE 3001
# Apply Alembic migrations then start uvicorn
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-3001}"]
