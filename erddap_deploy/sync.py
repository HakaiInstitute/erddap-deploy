import click
from git import Repo
from loguru import logger

from erddap_deploy.erddap import Erddap


@main.command()
@click.option("-r", "--repo", help="Path to git repo", type=str)
@click.option("-b", "--branch", help="Branch to sync from", type=str)
@click.option(
    "-p",
    "--local-repo-path",
    help="Where were to clone the repo",
    type=str,
    default="erddap-datasets",
    envvar="ERDDAP_DATASETS_DIR",
)
@click.option(
    "-f",
    "--hard-flag",
    help="Generate Hard flag for modified datasets",
    type=bool,
    default=False,
)
@click.option(
    "--hard-flag-dir",
    help="Directory to save hard flag",
    type=str,
    default="{ERDDAP_DATA}/erddap/hardFlag",
)
def sync(ctx, repo, branch, path, hard_flag, hard_flag_dir):
    """Sync datasets.xml from a git repo"""

    if not path.exists():
        logger.info(f"Clone repo {repo} to {path}")
        repo = Repo.clone_from(repo, path)
    else:
        repo = Repo(path)
    repo.git.checkout(branch)

    # Compare active dataset vs HEAD
    intial_erddap = Erddap(ctx.obj["datasets_xml"]).copy()
    repo.pull()
    updated_erddap = Erddap(ctx.obj["datasets_xml"]).copy()
    updated_erddap.to_xml()
    # Save updated datasets.xml
    updated_erddap.to_xml(path)
    diff = intial_erddap.diff(updated_erddap)
    if hard_flag:
        for datatset in diff:
            logger.info("Generate hard flag for {datatset.dataset_id}")
            (hard_flag_dir / datatset.dataset_id).write_text("")

    logger.info("Erddap datasets.xml has been updated")
