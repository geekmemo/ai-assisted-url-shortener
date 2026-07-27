import contextvars
import logging
import sys

# Per-request correlation ID, read directly at each log call site rather than
# via a logging.Filter — Filters attached to one logger/handler don't reliably
# apply to records that propagate through others (e.g. pytest's caplog), so
# explicit request_id=... in the message is simpler and doesn't depend on
# logging's propagation/filter internals.
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter('{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}')
    )
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
