# GSIN Backend (FastAPI)

## Run
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
cp config/.env.example config/.env
python backend/main.py
# http://localhost:8000  |  Docs: http://localhost:8000/docs
```

## Seed & Simulate
```bash
make seed
make simulate
```

## Notes
- Generates synthetic data if yfinance fails.
- MCN calls go through `backend/core/mcn_client.py` -> `mcn_layer/` (stub).
