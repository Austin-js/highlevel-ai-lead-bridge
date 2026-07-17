.PHONY: install dev lint format typecheck test coverage docker-build docker-up demo

install:
	python -m pip install -e .
	python -m pip install --group dev

dev:
	uvicorn app.main:app --reload

lint:
	ruff check .

format:
	ruff format .

typecheck:
	mypy app

test:
	pytest

coverage:
	coverage run -m pytest
	coverage report

docker-build:
	docker build -t highlevel-ai-lead-bridge .

docker-up:
	docker compose up --build

demo:
	python scripts/send_sample_event.py
