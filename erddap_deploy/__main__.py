import os
import sys
from pathlib import Path
import json

import click
import pytest
from git import Repo
from loguru import logger
from dotenv import load_dotenv

from erddap_deploy.erddap import Erddap
from erddap_deploy.monitor import uptime_kuma_monitor

# load .env file if available
load_dotenv(".env")


def get_erddap_env_variables():
    return {
        key.replace("ERDDAP_", ""): value
        for key, value in os.environ.items()
        if key.startswith("ERDDAP_")
    }


@click.group()
@click.option(
    "--datasets-xml",
    type=str,
    help="Glob expression path to datasets.xml (or multiple dataset xmls) use to generate ERDDAP datasets.xml. If not provided, ERDDAP will use the datasets.xml in the ERDDAP content directory.",
    default="**/datasets.d/*.xml|**/datasets.xml",
    envvar="ERDDAP_DATASETS_XML",
)
@click.option(
    "--recursive",
    "-r",
    type=bool,
    is_flag=True,
    default=True,
    show_default=True,
    help="Search for reference-datasets-xmls recursively",
    envvar="ERDDAP_RECURSIVE",
)
@click.option(
    "--active-datasets-xml",
    type=str,
    help="Path to active datasets.xml used by ERDDAP",
    default="/usr/local/tomcat/content/erddap/datasets.xml",
    show_default=True,
    envvar="ERDDAP_ACTIVE_DATASETS_XML",
)
@click.option(
    "--big-parent-directory",
    help="ERDDAP bigParentDirectory",
    type=str,
    default="/erddapData",
    show_default=True,
    envvar="ERDDAP_bigParentDirectory",
)
@click.option(
    "--secrets",
    help=(
        "JSON string of secrets to replace within `datasets.xml`. "
        "Secrets can also be defined via environment variables "
        "with the prefix `ERDDAP_SECRET_*` or "
        "the `ERDDAP_SECRETS` environment variable."
    ),
    type=str,
    envvar="ERDDAP_SECRETS",
)
@click.pass_context
@logger.catch(reraise=True)
def main(
    ctx,
    datasets_xml,
    recursive,
    active_datasets_xml,
    big_parent_directory,
    secrets,
):
    logger.debug("Run in debug mode")
    logger.debug(
        "ERDDAP ENV VARS: {}", [var for var in os.environ.keys() if "ERDDAP" in var]
    )
    logger.info("Load datasets.xml={} recursive={}", datasets_xml, recursive)
    if secrets:
        logger.info("Load secrets")
        secrets = json.loads(secrets)

    erddap = Erddap(datasets_xml, recursive=recursive, secrets=secrets)
    logger.info("Load active datasets.xml")
    active_erddap = (
        Erddap(active_datasets_xml, secrets=secrets)
        if Path(active_datasets_xml).exists()
        else None
    )
    if not active_erddap:
        logger.info(f"Active datasets.xml not found in {active_datasets_xml}")

    ctx.ensure_object(dict)
    ctx.obj.update(
        dict(
            erddap=erddap,
            active_erddap=active_erddap,
            datasets_xml=datasets_xml,
            active_datasets_xml=active_datasets_xml,
            recursive=recursive,
            bigParentDirectory=big_parent_directory,
        )
    )


@main.command()
@click.option("-o", "--output", help="Output file", type=str, default="{datasets_xml}")
@click.pass_context
@logger.catch
def save(ctx, output):
    """Save reference datasets.xml to active datasets.xml and include secrets."""
    logger.info("Convert to xml")
    output = output.format(**ctx.obj)
    return ctx.obj["erddap"].save(output=output)


@main.command()
@click.option(
    "-r",
    "--repo",
    help="Path to git repo",
    type=str,
    default=None,
    envvar="ERDDAP_DATASETS_REPO",
)
@click.option(
    "-b",
    "--branch",
    help="Branch to sync from",
    type=str,
    default=None,
    envvar="ERDDAP_DATASETS_REPO_BRANCH",
)
@click.option(
    "--github-token",
    help="Github token to access private repos",
    type=str,
    default=None,
    envvar="GITHUB_TOKEN",
)
@click.option(
    "--pull",
    help="Pull from remote",
    type=bool,
    default=False,
    is_flag=True,
    envvar="ERDDAP_DATASETS_REPO_PULL",
)
@click.option(
    "-p",
    "--local-repo-path",
    help="Where were to clone the repo",
    type=str,
    default="datasets-repo",
    envvar="ERDDAP_DATASETS_REPO_DIR",
)
@click.option(
    "-f",
    "--hard-flag",
    help="Generate Hard flag for modified datasets",
    type=bool,
    default=False,
    is_flag=True,
    envvar="ERDDAP_HARD_FLAG",
)
@click.option(
    "--hard-flag-dir",
    help="Directory to save hard flag",
    type=str,
    default="{bigParentDirectory}/erddap/hardFlag",
    envvar="ERDDAP_HARD_FLAG_DIR",
    show_default=True,
)
@click.pass_context
@logger.catch(reraise=True)
def sync(
    ctx, repo, branch, github_token, pull, local_repo_path, hard_flag, hard_flag_dir
):
    """Sync datasets.xml from a git repo"""

    # Format paths with context
    path_vars = get_erddap_env_variables()
    path_vars.update(ctx.obj)
    local_repo_path = local_repo_path.format(**path_vars)
    hard_flag_dir = Path(hard_flag_dir.format(**path_vars))

    # Get repo if not available and checkout branch and pull
    update_local_repository(repo, branch, github_token, pull, local_repo_path)

    # compare active dataset vs HEAD
    logger.info("Compare active dataset vs HEAD")
    ctx.obj["erddap"].load()
    erddap = ctx.obj["erddap"]
    active_erddap = ctx.obj["active_erddap"]

    if not erddap.datasets_xml:
        logger.error("Unable to sync since no datasets.xml found")
        sys.exit(1)

    if not active_erddap:
        logger.info("Save active datasets.xml")
        erddap.save(ctx.obj["active_datasets_xml"])
        diff = {id: None for id in erddap.datasets.keys()}
    else:
        diff = erddap.diff(active_erddap)

    # If any differences, update datasets.xml
    if diff:
        logger.info("Update datasets.xml")
        erddap.save(ctx.obj["active_datasets_xml"])

    if hard_flag:
        for datasetID, datasetDiff in diff.items():
            logger.info("Generate hard flag for {}", datasetID)
            logger.debug("Diff: {}", datasetDiff)
            (hard_flag_dir / datasetID).write_text("")

    logger.info("datasets.xml updated")


def update_local_repository(repo_url, branch, github_token, pull, local):
    """Get repo if not available and checkout branch and pull"""

    # Clone or load repo
    if not repo_url and not Path(local).exists():
        raise ValueError("Repo or local path is required")
    if not Path(local).exists() or not list(Path(local).glob("**/*")):
        logger.info(f"Clone repo {repo} to {local}")
        repo = Repo.clone_from(repo_url, local)
    else:
        repo = Repo(local)

    # Update origin url with github token
    if github_token:
        if "https://" in repo_url:
            repo_url = repo_url.replace("https://", f"https://{github_token}@")
        elif "git@" in repo_url:
            repo_url = repo_url.replace("git@", f"https://{github_token}@")
        else:
            logger.warning("Github token provided but repo url is not https or git@")

        logger.info("Update repo.git.origin url={}", repo_url)
        repo.git.remote("set-url", "origin", repo_url)

    # Checkout branch and pull
    if branch:
        logger.info(f"Checkout branch {branch}")
        repo.git.checkout(branch)

    # Pull from remote
    if pull:
        logger.info(f"Pull from remote")
        repo.git.pull()


@main.command()
@click.option(
    "-k",
    "--test-filter",
    help="Run tests by keyword expressions",
    type=str,
    default=None,
    envvar="ERDDAP_TEST_FILTER",
)
@click.option(
    "--active",
    help="Run tests on active datasets.xml, otherwise default to reference",
    type=bool,
    default=False,
    is_flag=True,
    envvar="ERDDAP_TEST_ACTIVE",
)
@click.pass_context
@logger.catch(reraise=True)
def test(ctx, test_filter, active):
    """Run a series of tests on repo ERDDAP datasets"""

    os.environ["ERDDAP_DATASETS_XML"] = (
        ctx.obj["active_datasets_xml"] if active else ctx.obj["datasets_xml"]
    )

    args = ["--pyargs", "erddap_deploy"]
    if test_filter:
        args.extend(["-k", test_filter])
    logger.info(f"Run pytest.main({args})")
    result = pytest.main(args).value
    if result:
        raise SystemExit(result)


@main.command()
@click.option(
    "--uptime-kuma-url",
    help="The URL of the uptime kuma instance",
    envvar="UPTIME_KUMA_URL",
)
@click.option(
    "--username",
    help="The username of the uptime kuma instance",
    envvar="UPTIME_KUMA_USERNAME",
)
@click.option(
    "--password",
    help="The password of the uptime kuma instance",
    envvar="UPTIME_KUMA_PASSWORD",
)
@click.option(
    "--token",
    help="The token of the uptime kuma instance",
    envvar="UPTIME_KUMA_TOKEN",
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
    "--dry-run",
    is_flag=True,
    help="Do not make any changes to uptime kuma",
    envvar="DRY_RUN",
    default=False,
)
@click.pass_context
@logger.catch(reraise=True)
def monitor(
    ctx,
    uptime_kuma_url: str,
    username: str,
    password: str,
    token: str = None,
    erddap_name: str = None,
    erddap_url: str = None,
    status_page_slug: str = None,
    status_page: Path = None,
    dry_run: bool = False,
):
    """Monitor ERDDAP deployment via uptime kuma status page.

    Required fields: uptime-kuma-url, username,password and token
    """

    if all([uptime_kuma_url, username, password, token]) is None:
        logger.warning("No uptime kuma credentials provided")
        sys.exit(1)
    elif (
        uptime_kuma_url is None or username is None or password is None or token is None
    ):
        missing = [
            parm
            for parm in [uptime_kuma_url, username, password, token]
            if parm is None
        ]
        logger.warning("Missing uptime kuma parameters: {}", missing)
        sys.exit(1)
    logger.info("Monitor ERDDAP deployment with uptime-kuma={}", uptime_kuma_url)
    if erddap_url is None:
        if os.environ.get("ERDDAP_baseHttpsUrl"):
            erddap_url = os.environ.get("ERDDAP_baseHttpsUrl") + "/erddap"
            logger.info("Using erddap_url=ERDDAP_baseHttpsUrl={}", erddap_url)
        elif os.environ.get("ERDDAP_baseUrl"):
            erddap_url = os.environ.get("ERDDAP_baseUrl") + "/erddap"
            logger.info("Using erddap_url=ERDDAP_baseUrl={}", erddap_url)
        else:
            logger.error("ERDDAP_baseUrl or ERDDAP_baseHttpsUrl is required")
            sys.exit(1)
    else:
        logger.info("Using erddap_url={}", erddap_url)
    if dry_run:
        logger.warning("Dry run mode enabled")
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
            datasets=list(ctx.obj["erddap"].datasets.values()),
            dry_run=dry_run,
        )
    except:
        logger.exception("Failed to monitor ERDDAP deployment", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.exception("Failed to execute command", exc_info=True)
        sys.exit(1)
