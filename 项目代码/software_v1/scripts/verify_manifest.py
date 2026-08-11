"""Validate deployment metadata without loading PyTorch weights."""

import os
from pathlib import Path

from app.ml.manifest import load_manifest, sha256_file


def main() -> None:
    path = Path(os.environ["MODEL_MANIFEST_PATH"]).resolve()
    manifest = load_manifest(path)
    root = path.parent.parent
    checkpoint = (root / manifest["checkpoint"]["relative_path"]).resolve()
    config = (root / manifest["model"]["config_relative_path"]).resolve()
    if manifest["status"] != "ready":
        raise RuntimeError("manifest status is not ready")
    if sha256_file(checkpoint) != manifest["checkpoint"]["sha256"]:
        raise RuntimeError("checkpoint SHA-256 mismatch")
    if sha256_file(config) != manifest["checkpoint"]["config_sha256"]:
        raise RuntimeError("config SHA-256 mismatch")
    print(f"manifest verified: {manifest['model']['version']}")


if __name__ == "__main__":
    main()
