FROM python:3.13.9-slim
RUN pip install --no-cache-dir uv==0.11.2
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY apps/api ./apps/api
COPY extensions/skills ./extensions/skills
ENV PYTHONPATH=/app/apps/api
EXPOSE 8000
CMD ["sh", "-c", "uv run --no-sync alembic -c apps/api/alembic.ini upgrade head && uv run --no-sync uvicorn app.main:app --host 0.0.0.0 --port 8000 --loop app.core.event_loop:database_event_loop"]
