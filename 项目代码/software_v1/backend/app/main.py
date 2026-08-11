from contextlib import asynccontextmanager
import os

from fastapi import FastAPI

from app.api.routes import router
from app.db.session import dispose_database, initialize_database
from app.ml.adapter import ModelAdapter
from app.ml.loader import ModelLoadError, load_model_from_environment
from app.ml.registry import register_runtime_model


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.model_adapter = None
    app.state.model_error = "model is not configured"
    factory = None
    if os.getenv("DATABASE_URL"):
        factory = initialize_database()
    model_configured = all(
        os.getenv(name)
        for name in ("MODEL_CONFIG_PATH", "MODEL_CHECKPOINT_PATH", "MODEL_MANIFEST_PATH")
    )
    if model_configured:
        try:
            loaded = load_model_from_environment()
            app.state.model_adapter = ModelAdapter(loaded)
            app.state.model_error = None
            if factory is not None:
                with factory() as db:
                    register_runtime_model(db, loaded)
        except ModelLoadError as exc:
            app.state.model_error = str(exc)
            if os.getenv("MODEL_PRELOAD_REQUIRED", "false").lower() == "true":
                raise
    try:
        yield
    finally:
        dispose_database()


app = FastAPI(title="Fake Review Detection API", version="1.0.0", lifespan=lifespan)
app.include_router(router)


@app.get("/", tags=["system"])
def root() -> dict[str, str]:
    return {"service": "fake-review-detection", "status": "ok"}
