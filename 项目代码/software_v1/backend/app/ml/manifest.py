import hashlib
import json
from pathlib import Path

SEMANTIC_LABELS = ["real", "misleading", "exaggerated", "advertising"]
BEHAVIOR_LABELS = ["normal", "review_manipulation", "crowdturfing", "bot_like", "insufficient_evidence"]
AUTHENTICITY_LABELS = ["real", "fake"]
MODEL_NAME = "albert-gru-gated-fusion"

class ManifestError(ValueError): pass

def load_manifest(path: str | Path) -> dict:
    file = Path(path)
    if not file.is_file(): raise ManifestError(f"manifest does not exist: {file}")
    try: data = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc: raise ManifestError("manifest is not valid JSON") from exc
    required = {"manifest_version", "status", "model", "checkpoint", "tokenizer", "dataset", "labels", "decision", "metrics", "runtime", "git_commit"}
    missing = required - data.keys()
    if missing: raise ManifestError(f"manifest missing fields: {sorted(missing)}")
    if data["model"].get("name") != MODEL_NAME:
        raise ManifestError(f"manifest model name must be {MODEL_NAME}")
    components = data["model"].get("components", {})
    if components != {"semantic": "ALBERT", "behavior": "GRU", "fusion": "vector_gate"}:
        raise ManifestError("manifest must describe the ALBERT-GRU vector-gate architecture")
    if data["labels"].get("authenticity") != AUTHENTICITY_LABELS:
        raise ManifestError("manifest authenticity label order does not match the model contract")
    if data["labels"].get("semantic") != SEMANTIC_LABELS or data["labels"].get("behavior") != BEHAVIOR_LABELS:
        raise ManifestError("manifest label order does not match the model contract")
    decision = data["decision"]
    threshold = decision.get("authenticity_threshold")
    if not isinstance(threshold, (int, float)) or not 0.0 <= float(threshold) <= 1.0:
        raise ManifestError("manifest authenticity threshold must be between zero and one")
    if decision.get("allow_type_override") is not False:
        raise ManifestError("manifest must disable type-based authenticity overrides")
    return data

def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""): digest.update(block)
    return digest.hexdigest()
