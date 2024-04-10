import json
import os
import re
import sys
from pathlib import Path
from typing import Union

import click
from dotenv import load_dotenv
from loguru import logger
from tqdm import tqdm
from uptime_kuma_api import UptimeKumaApi, exceptions

load_dotenv()


def get_erddap_protocol(dataset):
    if dataset.type.startswith("EDDTable"):
        return "tabledap"
    elif dataset.type.startswith("EDDGrid"):
        return "griddap"
    else:
        raise ValueError(f"Unknown dataset type {dataset.type}")


def dry_run(func):
    """Decorator to log the action that would be taken if dry_run is not enabled"""

    def wrapper(self, *args, **kwargs):
        if self.dry_run:
            logger.info(
                f"DRY-RUN: Would {func.__name__}(name={kwargs.get('name')}, ...)"
            )
        else:
            return func(self, *args, **kwargs)

    return wrapper


def retry_timeout(func, retries=3):
    """Decorator to retry a function"""

    def wrapper(*args, **kwargs):
        for i in range(retries):
            try:
                return func(*args, **kwargs)
            except exceptions.TimeoutError as e:
                logger.error("Error: {} retrying...", e)
                continue
        raise Exception(f"Failed to run {func.__name__} after 3 retries")

    return wrapper


class ErddapMonitor:
    def __init__(
        self,
        api: UptimeKumaApi,
        erddap_name: str,
        erddap_url: str,
        status_page_slug: str,
        status_page: dict,
        datasets: list = [],
        parent: dict = {},
        monitors: list = [],
        dry_run: bool = False,
        monitor_kwargs: dict = None,
    ):
        self.api = api
        self.erddap_name = erddap_name or re.search(r"https?://(.*)", erddap_url).group(
            1
        )
        self.erddap_url = erddap_url
        self.status_page_slug = status_page_slug or self._get_slug_from_erddap_name()
        self.status_page = status_page or {
            "title": self.erddap_name,
            "slug": self.status_page_slug,
        }
        self.datasets = datasets
        self.parent = parent or self.get_parent()
        self.monitors = monitors or self.get_monitors()
        self.dry_run = dry_run
        self.monitor_kwargs = monitor_kwargs

    def _get_slug_from_erddap_name(self) -> str:
        # replace all non alphanumeric characters with a dash
        slug = re.sub(r"[^a-zA-Z0-9-]+", "-", self.erddap_name).lower()
        # remove trailing dashes
        slug = re.sub(r"-$", "", slug)
        # remove duplicated dashes
        slug = re.sub(r"-+", "-", slug)
        if slug.endswith("-erddap"):
            slug = slug[:-7]
        return slug

    def _load_status_page_settings(self, status_page: Union[Path, dict]) -> dict:
        if isinstance(status_page, Path):
            return json.loads(status_page.read_text())
        elif isinstance(status_page, dict):
            return status_page
        else:
            return {}

    def make_erddap_pages_monitor(self, interval=60):
        pages = ["index.html", "tabledap/index.html", "griddap/index.html"]
        return [
            dict(
                name=page,
                description=f"ERDDAP Page Monitor for {page}",
                pathName=f"{self.erddap_name} / {page}",
                active="true",
                url=f"{self.erddap_url}/{page}",
                type="http",
                interval=interval,
            )
            for page in pages
        ]

    def make_dataset_page_monitor(self, dataset: dict, interval=60):
        name = f"{get_erddap_protocol(dataset)}/{dataset.dataset_id}.html"
        return dict(
            name=name,
            description=f"ERDDAP Dataset Page Monitor for {dataset.dataset_id}",
            pathName=f"{self.erddap_name} / {name}",
            active=dataset.active,
            url=f"{self.erddap_url}/{name}",
            type="http",
            interval=interval,
        )

    def make_dataset_data_monitor(self, dataset: dict, n_recs=10, interval=3600):
        name = f'{get_erddap_protocol(dataset)}/{dataset.dataset_id}.htmlTable?&orderByLimit("{n_recs}")'
        return dict(
            name=name,
            description=f"ERDDAP Dataset Data Monitor for {dataset.dataset_id}. Attemp to retrieve {n_recs} records",
            pathName=f"{self.erddap_name} / {name}",
            active=dataset.active,
            url=f"{self.erddap_url}/{name}",
            type="http",
            interval=interval,
        )

    def make_realtime_dataset_monitor(self, dataset: dict, dt="1day", interval=3600):
        name = f"{get_erddap_protocol(dataset)}/{dataset.dataset_id}.htmlTable?&time>now-{dt}"
        return dict(
            name=name,
            description=f"ERDDAP Dataset Realtime Monitor for {dataset.dataset_id}: last {dt}",
            pathName=f"{self.erddap_name} / {name}",
            active=dataset.active,
            url=f"{self.erddap_url}/{name}",
            type="http",
            interval=interval,
        )

    def get_monitors(self):
        """Get all monitors for the ERDDAP instance running on uptime kuma"""
        return [
            monitor
            for monitor in self.api.get_monitors()
            if monitor["pathName"].startswith(f"{self.erddap_name} / ")
        ]

    def get_parent(self):
        for parent in self.api.get_monitors():
            if parent["pathName"] == self.erddap_name:
                return parent

    @dry_run
    def add_monitor(self, *args, **kwargs):
        logger.info("Add monitor {}", kwargs.get("name"))
        return self.api.add_monitor(*args, **(self.monitor_kwargs or {}), **kwargs)

    @dry_run
    def pause_monitor(self, *args, **kwargs):
        logger.info("Pause monitor {}", kwargs.get("name"))
        return self.api.pause_monitor(kwargs["id"])

    @dry_run
    def resume_monitor(self, *args, **kwargs):
        logger.info("Resume monitor {}", kwargs.get("name"))
        return self.api.resume_monitor(kwargs["id"])

    def add_parent(self):
        logger.info(f"Adding parent {self.erddap_name}")
        response = self.api.add_monitor(
            name=self.erddap_name,
            type="group",
        )
        logger.info("{} monitorID={}", response["msg"], response["monitorID"])
        if "Added Successfully" not in response["msg"]:
            raise Exception(f"Failed to add parent: {response['msg']}")
        self.parent = self.api.get_monitor(response["monitorID"])

    def generate_monitors(self):
        """Generate expected monitors for the ERDDAP instance based on the dataset.xml file"""
        monitors = self.make_erddap_pages_monitor()
        for dataset in self.datasets:
            # TODO add manual overrides from .upttimekuma.yml
            monitors.append(self.make_dataset_page_monitor(dataset))
            if any(
                term in dataset.dataset_id.lower()
                for term in ("realtime", "Real-Time", "5min")
            ):
                monitors.append(self.make_realtime_dataset_monitor(dataset))
        return monitors

    def get_missing_monitors(self, monitors: list):
        monitor_pathnames = [monitor["pathName"] for monitor in self.get_monitors()]
        return [
            monitor
            for monitor in monitors
            if monitor["pathName"] not in monitor_pathnames
        ]

    def add_monitors(self, monitors: list):
        for monitor in monitors:
            response = self.add_monitor(
                parent=self.parent["id"],
                **{
                    key: value
                    for key, value in monitor.items()
                    if key not in ("pathName", "active")
                },
            )
            if not self.dry_run:
                logger.info("{} monitorID={}", response["msg"], response["monitorID"])

    def pause_monitors(self, expected_monitors: dict):
        for monitor in self.get_monitors():
            expected_monitor = [
                item
                for item in expected_monitors
                if item["pathName"] == monitor["pathName"]
            ]
            if not expected_monitor:
                continue
            if monitor["active"] and not expected_monitor[0]["active"]:
                self.pause_monitor(**monitor)

    def resume_monitors(self, expected_monitors: dict):
        for monitor in self.get_monitors():
            expected_monitor = [
                item
                for item in expected_monitors
                if item["pathName"] == monitor["pathName"]
            ]
            if not expected_monitor:
                continue
            if not monitor["active"] and expected_monitor[0]["active"]:
                self.resume_monitor(**monitor)

    def get_status_page(self):
        for status_page in self.api.get_status_pages():
            if status_page["slug"] == self.status_page_slug:
                return status_page

    def save_status_page(self, **kwargs):
        status_page = dict(
            title="ERDDAP Status: {erddap_name}",
            description=(
                f"ERDDAP Status Page for  {self.erddap_name} available at "
                f'<a href="{self.erddap_url}">{self.erddap_url}</a>'
            ),
            showTags=True,
            domainNameList=[self.erddap_url],
            footerText=f"<a href={self.erddap_url}>{self.erddap_name}</a>",
            publicGroupList=[
                {
                    "name": "ERDDAP Pages",
                    "weight": 1,
                    "monitorList": [
                        {"id": monitor["id"]}
                        for monitor in self.get_monitors()
                        if "index.html" in monitor["pathName"]
                    ],
                },
                {
                    "name": "ERDDAP Datasets",
                    "weight": 1,
                    "monitorList": [
                        {"id": monitor["id"]}
                        for monitor in self.get_monitors()
                        if (
                            "index.html" not in monitor["pathName"]
                            and "now-" not in monitor["pathName"]
                        )
                    ],
                },
                {
                    "name": "ERDDAP Realtime Datasets",
                    "weight": 1,
                    "monitorList": [
                        {"id": monitor["id"]}
                        for monitor in self.get_monitors()
                        if "now-" in monitor["pathName"]
                    ],
                },
            ],
        )
        if kwargs:
            kwargs.pop("slug", None)
            status_page.update(kwargs)
        return self.api.save_status_page(slug=self.status_page_slug, **status_page)

    def get_deleted_monitors(self):
        pass


def uptime_delete_monitors(api, delete_monitors, dry_run=False):
    @logger.catch()
    @retry_timeout
    def _delete_monitor(monitor):
        logger.info("Deleting monitor {}", monitor["pathName"])
        api.delete_monitor(monitor["id"])

    monitors_to_delete = [
        monitor
        for monitor in api.get_monitors()
        if monitor["url"] and re.match(delete_monitors, monitor["url"])
    ]
    logger.info("{} monitors matched to delete", len(monitors_to_delete))
    if dry_run:
        for monitor in monitors_to_delete:
            logger.info("Would delete monitor {}", monitor["pathName"])
        return
    for monitor in tqdm(
        monitors_to_delete,
        desc="Deleting monitors",
        unit="monitor",
        total=len(monitors_to_delete),
    ):
        _delete_monitor(monitor)


@logger.catch(reraise=True)
def uptime_kuma_monitor(
    uptime_kuma_url: str,
    username: str = None,
    password: str = None,
    token: str = None,
    erddap_name: str = None,
    erddap_url: str = None,
    status_page_slug: str = None,
    status_page: Path = None,
    datasets: str = "**/datasets.xml",
    delete_monitors: str = None,
    dry_run: bool = False,
    monitor_kwargs: dict = None,
    timeout: float = 10.0,
):
    # Connect to the uptime kuma instance
    with UptimeKumaApi(uptime_kuma_url, timeout=timeout) as api:
        api.login(username=username, password=password, token=token)

        if delete_monitors:
            uptime_delete_monitors(api, delete_monitors, dry_run=dry_run)
            return

        erddap_monitor = ErddapMonitor(
            api=api,
            erddap_name=erddap_name,
            erddap_url=erddap_url,
            status_page_slug=status_page_slug,
            status_page=status_page,
            datasets=datasets,
            dry_run=dry_run,
            monitor_kwargs=monitor_kwargs,
        )

        logger.info(f"Found {len(erddap_monitor.monitors)} erddap dataset monitors")
        if not erddap_monitor.datasets:
            return
        logger.info(f"Found {len(erddap_monitor.datasets)} datasets")

        # Generate expected erddap monitors
        expected_monitors = erddap_monitor.generate_monitors()

        # if parent doesn't exist, create it
        if not erddap_monitor.parent:
            erddap_monitor.add_parent()

        # Generate missing monitors
        missing_monitors = erddap_monitor.get_missing_monitors(expected_monitors)
        logger.info("{} monitors are missing", len(missing_monitors))
        erddap_monitor.add_monitors(missing_monitors)

        # Pause/Resume active datasets monitors
        erddap_monitor.pause_monitors(expected_monitors)
        erddap_monitor.resume_monitors(expected_monitors)

        # Maintain status pag
        status_page = erddap_monitor.get_status_page()
        if not status_page:
            logger.info(
                "Adding status page {} with title {}",
                erddap_monitor.status_page_slug,
                f"ERDDAP Status: {erddap_monitor.erddap_name}",
            )
            erddap_monitor.api.add_status_page(
                erddap_monitor.status_page_slug,
                f"ERDDAP Status: {erddap_monitor.erddap_name}",
            )
        logger.info("Updating status page {}", erddap_monitor.status_page_slug)
        erddap_monitor.save_status_page(**erddap_monitor.status_page)

        # Warn about deleted monitors
        deleted_monitors = erddap_monitor.get_deleted_monitors()
        if deleted_monitors:
            logger.warning("The following monitors were deleted: {}", deleted_monitors)

        logger.info("Uptime Kuma Monitoring Update Completed")


@click.command()
@click.option(
    "--uptime-kuma-url",
    help="The URL of the uptime kuma instance",
    envvar="UPTIME_KUMA_URL",
    required=True,
)
@click.option(
    "--username",
    help="The username of the uptime kuma instance",
    envvar="UPTIME_KUMA_USERNAME",
    required=True,
)
@click.option(
    "--password",
    help="The password of the uptime kuma instance",
    envvar="UPTIME_KUMA_PASSWORD",
    required=True,
)
@click.option(
    "--token",
    help="The token of the uptime kuma instance",
    envvar="UPTIME_KUMA_TOKEN",
    required=True,
)
@click.option(
    "--erddap-name",
    default=None,
    help="The name of the erddap instance used within human readable names (ex: some.url.com/erddap)",
    envvar="ERDDAP_NAME",
)
@click.option(
    "--erddap-url",
    type=str,
    default=None,
    help="The name of the erddap instance used within human readable names (ex: some.url.com/erddap)",
)
@click.option(
    "--status-page-slug",
    default=None,
    type=str,
    help="The slug of the status page",
    envvar="UPTIME_KUMA_STATUS_PAGE_SLUG",
)
@click.option(
    "--status-page",
    default=None,
    type=click.Path(exists=True),
    help="JSON file grouping the different items related to the uptime-kuma save_status_page.\n\n see  https://shorturl.at/FHKOP for more information.",
    envvar="UPTIME_KUMA_STATUS_PAGE",
)
@click.option(
    "--delete-monitors",
    default=None,
    type=str,
    help="Regex expression of monitors to delete. When define no new monitors will be added, only the ones matching the regex will be deleted",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Do not make any changes to uptime kuma",
    envvar="DRY_RUN",
    default=False,
)
@click.option(
    "--monitor-kwargs",
    type=str,
    help="Additional arguments to pass to the monitor creation",
    envvar="UPTIME_KUMA_MONITOR_KWARGS",
    default=None,
)
@click.option(
    "--timeout",
    default=10.0,
    type=float,
    help="Timeout for the API requests",
    envvar="UPTIME_KUMA_TIMEOUT",
)
@click.pass_context
@logger.catch(reraise=True)
def monitor(
    ctx,
    uptime_kuma_url: str,
    username: str,
    password: str,
    token: str,
    erddap_name: str = None,
    erddap_url: str = None,
    status_page_slug: str = None,
    status_page: Path = None,
    delete_monitors: str = None,
    dry_run: bool = False,
    monitor_kwargs: dict = None,
    timeout: float = 10.0,
):
    """Monitor ERDDAP deployment via uptime kuma status page."""

    if dry_run:
        logger.warning("Dry run mode enabled")

    logger.info("Monitor ERDDAP deployment with uptime-kuma={}", uptime_kuma_url)
    if erddap_url is None:
        logger.debug("Retrieve erddap_url from environment variables")
        if os.environ.get("ERDDAP_baseHttpsUrl"):
            erddap_url = os.environ.get("ERDDAP_baseHttpsUrl") + "/erddap"
            logger.debug("Using erddap_url=ERDDAP_baseHttpsUrl={}", erddap_url)
        elif os.environ.get("ERDDAP_baseUrl"):
            erddap_url = os.environ.get("ERDDAP_baseUrl") + "/erddap"
            logger.debug("Using erddap_url=ERDDAP_baseUrl={}", erddap_url)
        else:
            logger.error("ERDDAP_baseUrl or ERDDAP_baseHttpsUrl is required")
            sys.exit(1)
    else:
        logger.debug("Using erddap_url={}", erddap_url)

    if monitor_kwargs:
        try:
            monitor_kwargs = json.loads(monitor_kwargs)
        except json.JSONDecodeError:
            logger.error("Failed to parse monitor_kwargs as JSON")
            sys.exit(1)

    try:
        uptime_kuma_monitor(
            uptime_kuma_url,
            username,
            password,
            token=token,
            erddap_name=erddap_name,
            erddap_url=erddap_url,
            status_page_slug=status_page_slug,
            status_page=status_page,
            datasets=list(ctx.obj["erddap"].load().datasets.values()),
            delete_monitors=delete_monitors,
            dry_run=dry_run,
            monitor_kwargs=monitor_kwargs,
            timeout=timeout,
        )
    except Exception:
        logger.exception("Failed to monitor ERDDAP deployment", exc_info=True)


if __name__ == "__main__":
    monitor()
