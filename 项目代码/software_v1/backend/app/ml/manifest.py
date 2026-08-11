import hashlib
import json
from pathlib import Path

SEMANTIC_LABELS = ["real", "misleading", "exaggerated", "advertising"]
BEHAVIOR_LABELS = ["normal", "review_manipulation", "crowdturfing", "bot_like", "insufficient_evidence"]

class ManifestError(ValueError): pass

def load_manifest(path: str | Path) -> dict:
    file = Path(path)
    if not file.is_file(): raise ManifestError(f"manifest does not exist: {file}")
    try: data = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc: raise ManifestError("manifest is not valid JSON") from exc
    required = {"manifest_version", "model", "checkpoint", "tokenizer", "dataset", "labels", "metrics", "runtime", "git_commit"}
    missing = required - data.keys()
    if missing: raise ManifestError(f"manifest missing fields: {sorted(missing)}")
    if data["labels"].get("semantic") != SEMANTIC_LABELS or data["labels"].get("behavior") != BEHAVIOR_LABELS:
        raise ManifestError("manifest label order does not match the model contract")
    return data

def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""): digest.update(block)
    return digest.hexdigest()
