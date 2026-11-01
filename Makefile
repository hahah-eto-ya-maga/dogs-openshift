.PHONY: up down logs test smoke openshift
up:
	bash scripts/setup.sh
down:
	docker compose down
logs:
	docker compose logs -f --tail=100
test:
	python -m unittest discover -s tests -v
smoke:
	python scripts/smoke.py
openshift:
	bash scripts/deploy-openshift.sh
