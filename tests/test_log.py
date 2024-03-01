from pathlib import Path

import pandas as pd
import pytest

from erddap_deploy.log import ERDDAP_LOG


def test_parse_log_event():
    log = ERDDAP_LOG(dir="tests/data/logs")
    events = log.get_events(Path("tests/data/logs/log.txt").read_text())

    assert len(events) > 0
    assert isinstance(events, pd.DataFrame)
    assert "event_number" in events.columns
    assert "ip" in events.columns
    assert "status" in events.columns
    assert "elapsed_time" in events.columns


def test_parse_log_construct_events():
    log = ERDDAP_LOG(dir="tests/data/logs")
    events = log.get_constructings(Path("tests/data/logs/log.txt").read_text())

    assert len(events) > 0
    assert isinstance(events, pd.DataFrame)
    assert "datasetType" in events.columns
    assert "datasetID" in events.index.name
    assert "elapsed_time" in events.columns
    assert "extra" in events.columns


def test_logs_load():
    log = ERDDAP_LOG(dir="tests/data/logs", files="log*.txt")
    logs = log._load_logs()
    assert len(logs) > 0


def test_parse_logs():
    log = ERDDAP_LOG(dir="tests/data/logs", files="log*.txt")
    log.parse_logs()
    assert len(log.events) > 0
    assert len(log.datasetsStatus) > 0
    assert isinstance(log.events, pd.DataFrame)
    assert isinstance(log.datasetsStatus, pd.DataFrame)


def test_status_page_build(tmp_path):
    log = ERDDAP_LOG(dir="tests/data/logs", files="log*.txt")
    log.parse_logs()
    assert len(log.events) > 0
    assert len(log.datasetsStatus) > 0
    assert isinstance(log.events, pd.DataFrame)
    assert isinstance(log.datasetsStatus, pd.DataFrame)

    log.generate_status_page(Path("temp") / "status.html")


def test_events_page_build(tmp_path):
    log = ERDDAP_LOG(dir="tests/data/logs", files="log*.txt")
    log.parse_logs()
    assert len(log.events) > 0
    assert len(log.datasetsStatus) > 0
    assert isinstance(log.events, pd.DataFrame)
    assert isinstance(log.datasetsStatus, pd.DataFrame)

    log.generate_events_page(Path("temp") / "events.html")
