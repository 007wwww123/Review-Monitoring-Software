from fastapi import FastAPI

from app.api.routes import router

app = FastAPI(title="Fake Review Detection API", version="1.0.0")
app.include_router(router)


@app.get("/", tags=["system"])
def root() -> dict[str, str]:
    return {"service": "fake-review-detection", "status": "ok"}
