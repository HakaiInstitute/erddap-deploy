
import re
from pathlib import Path
from typing import Union
import json
from loguru import logger
from uptime_kuma_api import UptimeKumaApi


def get_erddap_protocol(dataset):
    if dataset.type.startswith("EDDTable"):
        return "tabledap"
    elif dataset.type.startswith("EDDGrid"):
        return "griddap"
    else:
        raise ValueError(f"Unknown dataset type {dataset.type}")


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
        name = f"{get_erddap_protocol(dataset)}/{dataset.dataset_id}.htmlTable?&orderByLimit(\"{n_recs}\")"
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
        return [
            monitor
            for monitor in self.api.get_monitors()
            if monitor["pathName"].startswith(f"{self.erddap_name} / ")
        ]

    def get_parent(self):
        for parent in self.api.get_monitors():
            if parent["pathName"] == self.erddap_name:
                return parent

    def add_parent(self):
        if self.dry_run:
            logger.info(f"Would add parent {self.erddap_name}")
        else:
            logger.info(f"Adding parent {self.erddap_name}")
            response = self.api.add_monitor(
                name=self.erddap_name,
                type="group",
            )
            logger.info("{} monitorID={}", response["msg"], response["monitorID"])
            if response["msg"] != "Added Successfully":
                raise Exception(f"Failed to add parent: {response['msg']}")
            self.parent = self.api.get_monitor(response["monitorID"])

    def generate_monitors(self):
        monitors = self.make_erddap_pages_monitor()
        for dataset in self.datasets:
            # TODO add manual overrides from .upttimekuma.yml
            monitors.append(self.make_dataset_page_monitor(dataset))
            if any(
                term in dataset.dataset_id.lower()
                for term in ("realtime", "Real-Time","5min")
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
            if self.dry_run:
                logger.info(f"Would add monitor {monitor}")
            else:
                logger.info(f"Adding monitor {monitor['name']}")
                response = self.api.add_monitor(
                    parent=self.parent["id"],
                    **{
                        key: value
                        for key, value in monitor.items()
                        if key not in ("pathName", "active")
                    },
                )
                logger.info("{} monitorID={}", response["msg"], response["monitorID"])

    def pause_monitors(self):
        expected_monitors = {
            monitor["pathName"]: monitor["active"] for monitor in self.get_monitors()
        }
        for monitor in self.get_monitors():
            if monitor["active"] and not expected_monitors.get(
                monitor["pathName"], True
            ):
                if self.dry_run:
                    logger.info(f"Would pause monitor {monitor}")
                else:
                    logger.info(f"Pausing monitor {monitor}")
                    self.api.pause_monitor(monitor["id"])

    def resume_monitors(self):
        expected_monitors = {
            monitor["pathName"]: monitor["active"] for monitor in self.get_monitors()
        }
        for monitor in self.get_monitors():
            if not monitor["active"] and expected_monitors.get(
                monitor["pathName"], False
            ):
                if self.dry_run:
                    logger.info(f"Would resume monitor {monitor}")
                else:
                    logger.info(f"Pausing monitor {monitor}")
                    self.api.resume_monitor(monitor["id"])


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
                        if ("index.html" not in monitor["pathName"] and "now-" not in monitor["pathName"])
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
    dry_run: bool = False,
):
    # Connect to the uptime kuma instance
    with UptimeKumaApi(uptime_kuma_url) as api:
        api.login(username=username, password=password, token=token)

        erddap_monitor = ErddapMonitor(
            api=api,
            erddap_name=erddap_name,
            erddap_url=erddap_url,
            status_page_slug=status_page_slug,
            status_page=status_page,
            datasets=datasets,
            dry_run=dry_run,
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
        erddap_monitor.pause_monitors()
        erddap_monitor.resume_monitors()

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