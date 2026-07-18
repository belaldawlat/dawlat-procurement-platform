"""Shared pytest configuration for Phase 19 dashboard intelligence tests."""

from __future__ import annotations

import sys
import types
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = PROJECT_ROOT / "app"

if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))


# Pure snapshot and helper tests must run in minimal CI environments even when
# the optional Streamlit runtime is not installed. Production execution still
# uses the real Streamlit package.
try:
    import streamlit  # noqa: F401
except ModuleNotFoundError:
    streamlit_stub = types.ModuleType("streamlit")

    def _no_op(*args: object, **kwargs: object) -> None:
        return None

    streamlit_stub.title = _no_op
    streamlit_stub.caption = _no_op
    streamlit_stub.subheader = _no_op
    streamlit_stub.info = _no_op
    streamlit_stub.success = _no_op
    streamlit_stub.warning = _no_op
    streamlit_stub.error = _no_op
    streamlit_stub.metric = _no_op
    streamlit_stub.dataframe = _no_op
    streamlit_stub.bar_chart = _no_op
    streamlit_stub.json = _no_op
    streamlit_stub.columns = lambda count: [streamlit_stub] * count
    streamlit_stub.expander = lambda *args, **kwargs: streamlit_stub
    streamlit_stub.__enter__ = lambda self: self
    streamlit_stub.__exit__ = lambda self, *args: False
    sys.modules["streamlit"] = streamlit_stub