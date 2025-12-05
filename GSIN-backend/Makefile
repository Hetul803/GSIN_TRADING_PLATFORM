PY=python

.PHONY: setup api.run seed simulate

setup:
	$(PY) -m venv .venv && . .venv/bin/activate && pip install -r backend/requirements.txt

api.run:
	. .venv/bin/activate && $(PY) backend/main.py

seed:
	API_URL=http://localhost:8000 $(PY) scripts/seed_strategies.py

simulate:
	API_URL=http://localhost:8000 $(PY) scripts/simulate_week.py
