"""Safe, uniform error responses: `{error, code}` with no internal detail (NFR-SEC-002)."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ApiError(Exception):
    """Raise from a route to return `{error, code}` with a chosen status."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def error_body(code: str, message: str) -> dict[str, str]:
    return {"error": message, "code": code}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(error_body(exc.code, exc.message), status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, __: RequestValidationError) -> JSONResponse:
        # Never echo the offending payload back to the client.
        return JSONResponse(
            error_body("ValidationError", "The request was not valid."), status_code=400
        )

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, __: Exception) -> JSONResponse:
        return JSONResponse(
            error_body("InternalError", "Something went wrong. Please try again."),
            status_code=500,
        )


__all__ = ["ApiError", "error_body", "register_error_handlers"]
