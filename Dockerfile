FROM python:3.13 AS builder

WORKDIR /accounts_app

RUN apt-get update && apt-get install -y --no-install-recommends

RUN pip install uv

COPY pyproject.toml ./
RUN uv pip install --system -e . --no-cache


FROM python:3.13-slim AS runtime

WORKDIR /accounts_app

COPY --from=builder /usr/local/lib/python3.13 /usr/local/lib/python3.13
COPY --from=builder /usr/local/bin /usr/local/bin

COPY . .

CMD ["uvicorn", "src.interfaces.api.app:app", "--loop", "uvloop", "--host", "0.0.0.0", "--port", "8000", "--reload"]
