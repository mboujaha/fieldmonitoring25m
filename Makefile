.PHONY: up-dev down logs api-shell migrate test-api test-web

up-dev:
	docker compose --profile dev up --build

down:
	docker compose down

logs:
	docker compose logs -f --tail=200

api-shell:
	docker compose --profile dev exec api /bin/sh

migrate:
	docker compose --profile dev exec api alembic -c /workspace/apps/api/alembic.ini upgrade head

test-api:
	docker compose --profile dev exec api pytest -q

test-web:
	docker compose --profile dev exec web npm run typecheck
