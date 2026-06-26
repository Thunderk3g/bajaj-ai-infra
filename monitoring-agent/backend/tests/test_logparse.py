"""Tests for app.engine.split_log_line — RFC3339 stamp splitting (§3 logs)."""
from app import engine


def test_splits_leading_rfc3339_nano_stamp():
    out = engine.split_log_line("2026-06-26T12:04:01.123456789Z INFO started up")
    assert out == {"ts": "2026-06-26T12:04:01.123456789Z", "text": "INFO started up"}


def test_splits_plain_rfc3339_stamp():
    out = engine.split_log_line("2026-06-26T12:04:01Z hello world")
    assert out["ts"] == "2026-06-26T12:04:01Z"
    assert out["text"] == "hello world"


def test_offset_timezone_stamp():
    out = engine.split_log_line("2026-06-26T12:04:01+05:30 line")
    assert out["ts"] == "2026-06-26T12:04:01+05:30"
    assert out["text"] == "line"


def test_line_without_stamp_keeps_ts_none():
    out = engine.split_log_line("just a bare log line")
    assert out["ts"] is None
    assert out["text"] == "just a bare log line"


def test_strips_trailing_newline_and_cr():
    out = engine.split_log_line("2026-06-26T12:04:01Z payload\r\n")
    assert out["text"] == "payload"


def test_empty_line():
    assert engine.split_log_line("") == {"ts": None, "text": ""}
