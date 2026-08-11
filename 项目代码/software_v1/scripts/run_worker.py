"""Run the single database-backed GPU worker."""

import os
import signal
import time

from app.db.session import dispose_database, initialize_database
from app.ml.adapter import ModelAdapter
from app.ml.loader import load_model_from_environment
from app.ml.registry import register_runtime_model
from app.services.worker import BatchDetectionWorker


running = True


def stop_worker(*_args) -> None:
    global running
    running = False


def main() -> None:
    signal.signal(signal.SIGINT, stop_worker)
    signal.signal(signal.SIGTERM, stop_worker)
    factory = initialize_database()
    loaded = load_model_from_environment()
    adapter = ModelAdapter(loaded)
    with factory() as db:
        register_runtime_model(db, loaded)
    interval = max(float(os.getenv("WORKER_POLL_SECONDS", "2")), 0.2)
    try:
        while running:
            with factory() as db:
                processed = BatchDetectionWorker(db, adapter).run_once()
            if not processed:
                time.sleep(interval)
    finally:
        dispose_database()


if __name__ == "__main__":
    main()
