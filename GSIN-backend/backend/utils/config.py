from dotenv import dotenv_values
from pathlib import Path

CFG_PATH = Path(__file__).resolve().parents[2] / "config" / ".env"
cfg = dotenv_values(str(CFG_PATH)) if CFG_PATH.exists() else {}

DATABASE_URL = cfg.get("DATABASE_URL", "sqlite:///gsin.db")
DECAY_RATE = float(cfg.get("DECAY_RATE", 0.05))
LEARNING_RATE = float(cfg.get("LEARNING_RATE", 0.2))
