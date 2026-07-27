import contextvars
import json
import logging
import sys

# Per-request correlation ID, read directly at each log call site rather than
# via a logging.Filter — Filters attached to one logger/handler don't reliably
# apply to records that propagate through others (e.g. pytest's caplog), so
# explicit request_id=... in the message is simpler and doesn't depend on
# logging's propagation/filter internals.
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


class JsonFormatter(logging.Formatter):
    """Builds the log line via json.dumps rather than string interpolation.

    A prior version interpolated the message directly into a JSON-shaped
    string template, which produced invalid JSON whenever the message
    contained a quote or newline — exactly what exception text (the
    content of our own failure-path warning logs) commonly contains.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        return json.dumps(payload)


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
