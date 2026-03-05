.PHONY: dev down migrate mm test logs shell pull-image

dev:
	docker compose up --build

down:
	docker compose down

migrate:
	docker compose exec backend alembic upgrade head

mm:
	docker compose exec backend alembic revision --autogenerate -m "$(msg)"

test:
	docker compose exec backend pytest tests/ -v --asyncio-mode=auto

logs:
	docker compose logs -f backend

shell:
	docker compose exec backend python

pull-image:
	docker pull alpine:latest
