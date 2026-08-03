# NUDGE backend — multi-stage build
#
# Stage 1 compiles wheels so the runtime image carries no build toolchain.
# Stage 2 runs as a non-root user with no compilers present.

# ---------- builder ----------
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update \
 && apt-get install -y --no-install-recommends gcc python3-dev \
 && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt


# ---------- runtime ----------
FROM python:3.11-slim AS production

# scrot/xvfb back pyautogui's screen access on Linux hosts
RUN apt-get update \
 && apt-get install -y --no-install-recommends scrot xvfb curl \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --create-home --shell /usr/sbin/nologin nudge

WORKDIR /app

COPY --from=builder /wheels /wheels
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt \
 && rm -rf /wheels

COPY --chown=nudge:nudge backend/ ./backend/

USER nudge

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    NUDGE_TOKEN_TTL_MINUTES=15

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
