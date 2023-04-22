import logging
import random
import string
import time

from fastapi import Request, Response
from starlette.middleware.base import RequestResponseEndpoint

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import Message


def generate_trace_id() -> str:
    res = ''.join(random.choices(string.ascii_uppercase +
                                 string.digits, k=10))
    return res.lower()


class RequestContextLogMiddleware(BaseHTTPMiddleware):
    request_logger: logging.Logger

    def __init__(self, app, request_logger: logging.Logger):
        super().__init__(app)
        self.request_logger = request_logger

    async def set_body(self, request: Request):
        receive_ = await request._receive()

        async def receive() -> Message:
            return receive_

        request._receive = receive

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        trace_id = generate_trace_id()
        start_time = time.time()
        request.scope["trace_id"] = trace_id
        await self.set_body(request)
        json_body = await request.json()
        response: Response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        log_payload = {
            "trace_id": trace_id,
            "request": {
                "method": request.method,
                "url": str(request.url),
                "headers": request.headers,
                "params": {
                    "path-params": request.path_params,
                    "query-params": request.query_params
                },
                "body": json_body
            },
            "response": {
                "status_code": response.status_code,
            },
            "process_time_seconds": process_time
        }
        self.request_logger.info("%s", log_payload)
        return response
