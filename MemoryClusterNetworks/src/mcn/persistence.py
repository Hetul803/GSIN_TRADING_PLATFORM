# src/mcn/persistence.py
import json, os, time
import numpy as np

def _ensure_dir(path: str):
    d = os.path.dirname(path)
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)

def save_state(path: str, *, vectors: np.ndarray, meta: list, values: np.ndarray, birth: np.ndarray,
               lambda_decay: float, dim: int, policy: dict, extra: dict | None = None):
    """
    Save MCN state to a directory or NPZ file.
    - path: if endswith ".npz" -> NPZ; else creates a folder with separate files.
    """
    _ensure_dir(path)
    payload = {
        "vectors": vectors.astype("float32"),
        "values": values.astype("float32"),
        "birth": birth.astype("float64"),
        "lambda_decay": float(lambda_decay),
        "dim": int(dim),
        "saved_at": float(time.time())
    }
    meta_json = json.dumps(meta, ensure_ascii=False)
    policy_json = json.dumps(policy or {})
    extra_json = json.dumps(extra or {})

    if path.endswith(".npz"):
        # Single-file save
        np.savez(
            path,
            vectors=payload["vectors"],
            values=payload["values"],
            birth=payload["birth"],
            lambda_decay=payload["lambda_decay"],
            dim=payload["dim"],
            saved_at=payload["saved_at"],
            meta_json=meta_json,
            policy_json=policy_json,
            extra_json=extra_json
        )
    else:
        # Directory layout
        os.makedirs(path, exist_ok=True)
        np.save(os.path.join(path, "vectors.npy"), payload["vectors"])
        np.save(os.path.join(path, "values.npy"), payload["values"])
        np.save(os.path.join(path, "birth.npy"), payload["birth"])
        with open(os.path.join(path, "meta.json"), "w", encoding="utf-8") as f:
            f.write(meta_json)
        with open(os.path.join(path, "policy.json"), "w", encoding="utf-8") as f:
            f.write(policy_json)
        with open(os.path.join(path, "extra.json"), "w", encoding="utf-8") as f:
            f.write(extra_json)
        with open(os.path.join(path, "attrs.json"), "w", encoding="utf-8") as f:
            json.dump({
                "lambda_decay": payload["lambda_decay"],
                "dim": payload["dim"],
                "saved_at": payload["saved_at"]
            }, f)

def load_state(path: str):
    """
    Load MCN state saved by save_state(...).
    Returns dict with keys:
      vectors, meta, values, birth, lambda_decay, dim, policy (dict), extra (dict)
    """
    if path.endswith(".npz"):
        z = np.load(path, allow_pickle=True)
        vectors = z["vectors"]
        values = z["values"]
        birth = z["birth"]
        lambda_decay = float(z["lambda_decay"])
        dim = int(z["dim"])
        meta = json.loads(str(z["meta_json"]))
        policy = json.loads(str(z["policy_json"]))
        extra = json.loads(str(z["extra_json"]))
        return dict(vectors=vectors, meta=meta, values=values, birth=birth,
                    lambda_decay=lambda_decay, dim=dim, policy=policy, extra=extra)
    else:
        import os, json
        vectors = np.load(os.path.join(path, "vectors.npy"))
        values = np.load(os.path.join(path, "values.npy"))
        birth = np.load(os.path.join(path, "birth.npy"))
        with open(os.path.join(path, "meta.json"), "r", encoding="utf-8") as f:
            meta = json.load(f)
        with open(os.path.join(path, "policy.json"), "r", encoding="utf-8") as f:
            policy = json.load(f)
        extra = {}
        attrs_path = os.path.join(path, "attrs.json")
        if os.path.exists(attrs_path):
            with open(attrs_path, "r", encoding="utf-8") as f:
                attrs = json.load(f)
                lambda_decay = float(attrs.get("lambda_decay", 1e-6))
                dim = int(attrs.get("dim", vectors.shape[1]))
        else:
            lambda_decay = 1e-6
            dim = vectors.shape[1]
        extra_path = os.path.join(path, "extra.json")
        if os.path.exists(extra_path):
            with open(extra_path, "r", encoding="utf-8") as f:
                extra = json.load(f)
        return dict(vectors=vectors, meta=meta, values=values, birth=birth,
                    lambda_decay=lambda_decay, dim=dim, policy=policy, extra=extra)
