"""Throwaway probe: does a user middleware see a ServerErrorMiddleware 500?"""

import starlette
import fastapi
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware


class Stamp(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Request-ID"] = "stamped"
        return response


app = FastAPI()
app.add_middleware(Stamp)


@app.exception_handler(Exception)
async def handler(_request, exc):
    return JSONResponse(status_code=500, content={"error": "boom"})


@app.get("/ok")
async def ok():
    return {"ok": True}


@app.get("/boom")
async def boom():
    raise RuntimeError("boom")


client = TestClient(app, raise_server_exceptions=False)
print("versions:", starlette.__version__, fastapi.__version__)
print("ok:", client.get("/ok").status_code, dict(client.get("/ok").headers))
five = client.get("/boom")
print("500:", five.status_code, five.headers.get("x-request-id"), five.text[:80])
print("404:", client.get("/nope").status_code, client.get("/nope").headers.get("x-request-id"))
