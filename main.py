import pyjokes
from fastapi import FastAPI
from prometheus_client import make_asgi_app

app = FastAPI(title="Hello Joker")
app.mount("/metrics", make_asgi_app())


@app.get("/")
async def root() -> dict[str, str]:
    return {"random_joke": pyjokes.get_joke(language="en", category="neutral")}


@app.get("/healthz")
async def health() -> dict[str, str]:
    return {"status": "ok"}
