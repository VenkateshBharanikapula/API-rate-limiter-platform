.PHONY: up down build logs shell migrate makemigration test test-cov lint

up:
	docker-compose up

build:
	docker-compose up --build

down:
	docker-compose down

logs:
	docker-compose logs -f fastapi

shell:
	docker-compose exec fastapi /bin/bash

migrate:
	docker-compose exec fastapi alembic upgrade head

makemigration:
	docker-compose exec fastapi alembic revision --autogenerate -m "$(msg)"

test:
	pytest

test-cov:
	pytest --cov=app --cov-report=term-missing --cov-report=html

lint:
	ruff check app tests

locust:
	locust -f locust/locustfile.py --host=http://localhost:8000
