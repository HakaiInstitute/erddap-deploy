import os
import re
from pathlib import Path

import pandas as pd
import plotly.express as px
from jinja2 import Environment, FileSystemLoader

environment = Environment(loader=FileSystemLoader(Path(__file__).parent / "templates"))


event_start_items = ["event_number", "timestamp", "user", "ip", "action", "url"]
event_end_items = ["event_number", "ip", "status", "elapsed_time"]

construct_start_items = ["constructing", "datasetType", "datasetID"]
construct_finished_items = [
    "datasetType",
    "datasetID",
    "constructor",
    "finished.",
    "elapsed_time",
    "extra",
]

ERDDAP_Environment = {
    key.replace("ERDDAP_", ""): value
    for key, value in os.environ.items()
    if key.startswith("ERDDAP_")
}


class ERDDAP_LOG:
    def __init__(self, dir, files="log*.txt", recursive=True, logs=[]):
        self.dir = dir
        self.files = files
        self.logs = logs
        self.events = None
        self.datasetsStatus = None

    def find_logs(self):
        """Find all log files."""
        return list(Path(self.dir).glob(self.files))

    def _load_logs(self):
        """Load all log files."""
        logs = pd.DataFrame(dict(file=self.find_logs()))
        logs["mtime"] = logs.apply(lambda row: row.file.stat().st_mtime, axis=1)
        logs["size"] = logs.apply(lambda row: row.file.stat().st_size, axis=1)
        return logs.set_index("file").sort_values("mtime", ascending=True)

    def parse_logs(self):
        """Parse all log files and return a list of dictionaries."""
        log_files = list(Path(self.dir).glob(self.files))
        if not log_files:
            raise FileNotFoundError(f"No log files found in {self.dir}/{self.files}")
        for file in log_files:
            self.parse_log(file)

    def parse_log(self, log_file: Path):
        """Parse the log file and return a list of dictionaries."""
        log = log_file.read_text()
        self.events = pd.concat(
            [
                item
                for item in [
                    self.events,
                    self.get_events(log).assign(log=log_file.name),
                ]
                if item is not None
            ]
        )
        self.datasetsStatus = pd.concat(
            [
                item
                for item in [
                    self.datasetsStatus,
                    self.get_constructings(log).assign(log=log_file.name),
                ]
                if item is not None
            ]
        )

    @staticmethod
    def get_events(log):
        """Return a list of events from the log."""

        def _get_event_dict(event, labels):
            return dict(
                zip(
                    labels,
                    log[event.start() : event.end()][5:].split(" "),
                )
            )

        event_start = pd.DataFrame(
            [
                _get_event_dict(event, event_start_items)
                for event in re.finditer(r"\{\{\{\{\#[^\n]+", log)
            ]
        )
        event_end = pd.DataFrame(
            [
                _get_event_dict(event, event_end_items)
                for event in re.finditer(r"\}\}\}\}\#[^\n]+", log)
            ]
        )

        return event_start.merge(event_end, on=["event_number", "ip"])

    @staticmethod
    def get_constructings(log, get="latest"):
        """Return a list of constructing events."""

        def _parse_constructing(event, labels):
            return {
                **dict(
                    zip(
                        labels,
                        re.split("\s+", log[event.start() : event.end()][4:]),
                    )
                ),
                "start": event.start(),
                "end": event.end(),
            }

        def _parse_constructing_error(event, error_max_length=1000):
            message = log[event.start() : event.end()].split("=")[-1].split(" ", 1)
            return {
                "datasetID": message[0],
                "error_extra": message[1] if len(message) == 2 else None,
                "error_start": event.start(),
                "error_end": event.end(),
                "error_message": log[event.start() : (event.end() + error_max_length)]
                .split("\n")[2]
                .split(":", 1)[1],
            }

        construct_start = pd.DataFrame(
            [
                _parse_constructing(event, construct_start_items)
                for event in re.finditer(r"\*\*\* constructing \w+ \w+", log)
            ]
        ).drop(columns=["constructing"])
        construct_end = pd.DataFrame(
            [
                _parse_constructing(event, construct_finished_items)
                for event in re.finditer(
                    r"\*\*\* \w+ \w+ constructor finished\. .*", log
                )
            ]
        ).drop(columns=["constructor", "finished."])

        errors = pd.DataFrame(
            [
                _parse_constructing_error(event)
                for event in re.finditer(
                    r"datasets.xml error on line \#\d+\nWhile trying to load datasetID=.*",
                    log,
                )
            ]
        )

        # Merge the start and end constructing events
        construct = pd.merge_asof(
            construct_start,
            construct_end,
            by=["datasetType", "datasetID"],
            on="start",
            suffixes=("_start", "_end"),
            direction="forward",
        )
        # Merge the errors with the constructing events
        construct = pd.merge_asof(
            construct,
            errors,
            by="datasetID",
            left_on="start",
            right_on="error_start",
            direction="forward",
        ).drop(columns=["index"], errors="ignore")

        return construct.set_index("datasetID")

    def generate_status_page(self, output="docs/status.html"):
        """Generate a status page that list the status of each dataset."""
        log_txt = f"logArchivedAt{pd.Timestamp.utcnow().isoformat()[:19]}.txt".replace(
            ":", "."
        )
        latest_status = (
            self.datasetsStatus.replace({"log": {"log.txt": log_txt}})
            .sort_values(["log", "start"])
            .groupby("datasetID")
            .tail(1)
            .fillna("")
        )

        status_html = environment.get_template("status.html").render(
            latest_status=latest_status[
                ["datasetType", "elapsed_time", "error_extra", "error_message", "log"]
            ],
            **ERDDAP_Environment,
        )
        output = Path(output)
        if not output.parent.exists():
            output.parent.mkdir(parents=True)

        output.write_text(status_html)

    def generate_events_page(self, output="docs/events.html"):
        """Generate a events page."""
        # generate the events page
        # last 24 hours
        e24h = px.histogram(
            self.events.query(
                f"timestamp>'{pd.Timestamp.utcnow()-pd.Timedelta('24h')}'"
            ),
            x="timestamp",
            title="Last 24 hours",
        )

        # last 7 days
        e7d = px.histogram(
            self.events.query(
                f"timestamp>'{pd.Timestamp.utcnow()-pd.Timedelta('7d')}'"
            ),
            x="timestamp",
            title="Last 7 days",
        )

        # last 30 days
        e30d = px.histogram(
            self.events.query(
                f"timestamp>'{pd.Timestamp.utcnow()-pd.Timedelta('30d')}'"
            ),
            x="timestamp",
            title="Last 30 days",
        )

        # last 365 days
        e365d = px.histogram(
            self.events.query(
                f"timestamp>'{pd.Timestamp.utcnow()-pd.Timedelta('365d')}'"
            ),
            x="timestamp",
            title="Last 365 days",
        )

        # all time
        eall = px.histogram(self.events, x="timestamp", title="All time")

        events_html = environment.get_template("events.html").render(
            e24h=e24h.to_html(),
            e7d=e7d.to_html(),
            e30d=e30d.to_html(),
            e365d=e365d.to_html(),
            eall=eall.to_html(),
            **ERDDAP_Environment,
        )
        output = Path(output)
        if not output.parent.exists():
            output.parent.mkdir(parents=True)

        output.write_text(events_html)
