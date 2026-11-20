"""The API error envelope: every non-2xx response has the body {code, message, details?}."""
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger(__name__)


class ApiError(Exception):
    """Raise from any route or service to answer with the error envelope."""

    def __init__(self, status: int, code: str, message: str, details: dict | None = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details


def not_found(what: str = "Resource") -> ApiError:
    """Return the 404 error for something that doesn't exist."""
    return ApiError(404, "not_found", f"{what} not found.")


def error_response(status: int, code: str, message: str, details: dict | None = None,
                   headers: dict | None = None) -> JSONResponse:
    """Return a response with the error envelope as its body."""
    body = {"code": code, "message": message}
    if details is not None:
        body["details"] = details
    return JSONResponse(body, status_code=status, headers=headers)


_HTTP_CODES = {
    400: ("bad_request", "The request isn't valid."),
    401: ("unauthenticated", "Sign in to continue."),
    403: ("forbidden", "You can't do that."),
    404: ("not_found", "Not found."),
    405: ("method_not_allowed", "That method isn't allowed here."),
}


def _api_error(_request: Request, exc: ApiError) -> JSONResponse:
    """Answer an ApiError with its own status and code."""
    return error_response(exc.status, exc.code, exc.message, exc.details)


def _http_error(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Answer the framework's HTTP errors (404, 405...) with the envelope."""
    code, message = _HTTP_CODES.get(exc.status_code, (f"http_{exc.status_code}", "Request failed."))
    if isinstance(exc.detail, str) and exc.detail and exc.status_code not in _HTTP_CODES:
        message = exc.detail
    return error_response(exc.status_code, code, message, headers=getattr(exc, "headers", None))


def _validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
    """Answer a request body that doesn't match its model with 422 invalid_request."""
    errors = [
        {"loc": list(err.get("loc", ())), "msg": str(err.get("msg", "")),
         "type": str(err.get("type", ""))}
        for err in exc.errors()
    ]
    return error_response(422, "invalid_request", "The request isn't valid.", {"errors": errors})


def _unexpected_error(_request: Request, exc: Exception) -> JSONResponse:
    """Log an unexpected error and answer 500 without the stack trace."""
    log.exception("Unhandled error", exc_info=exc)
    return error_response(500, "internal_error", "Something went wrong on the server.")


def install_error_handlers(app: FastAPI) -> None:
    """Make every error the app raises answer with the envelope."""
    app.add_exception_handler(ApiError, _api_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(Exception, _unexpected_error)
