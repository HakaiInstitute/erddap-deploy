from click.testing import CliRunner

from erddap_deploy.__main__ import main

TEST_REPO = "https://github.com/HakaiInstitute/erddap-deploy.git"


def run_cli(*args):
    runner = CliRunner()
    return runner.invoke(main, args, catch_exceptions=False)


def test_erddap_deploy_help():
    result = run_cli("--help")
    assert result.exit_code == 0


class TestErddapDeployTest:
    def test_test(self):
        result = run_cli("test")
        assert result.exit_code == 0

    def test_test_help(self):
        result = run_cli("test", "--help")
        assert result.exit_code == 0


class TestErddapDeploySync:
    def test_sync(self, tmp_path):
        active_datasets_xml = tmp_path / "datasets.xml"
        local_repo_path = tmp_path / "erddap-datasets"
        result = run_cli(
            "--datasets-xml",
            local_repo_path / "**/datasets.d/*.xml",
            "--active-datasets-xml",
            active_datasets_xml,
            "sync",
            "--repo",
            TEST_REPO,
            "--branch",
            "main",
            "--local-repo-path",
            local_repo_path,
        )
        assert result.exit_code == 0

    def test_sync_help(self):
        result = run_cli("sync", "--help")
        assert result.exit_code == 0

    def test_sync_hard_flag(self, tmp_path):
        active_datasets_xml = tmp_path / "datasets.xml"
        local_repo_path = tmp_path / "erddap-datasets"
        hard_flag_dir = tmp_path / "hardFlag"
        hard_flag_dir.mkdir()

        # iniatialize datasets.xml
        initial_args = (
            "--datasets-xml",
            local_repo_path / "**/datasets.d/*.xml",
            "--active-datasets-xml",
            active_datasets_xml,
            "sync",
            "--repo",
            TEST_REPO,
            "--branch",
            "main",
            "--local-repo-path",
            local_repo_path,
        )
        result = run_cli(
            *initial_args,
        )
        assert result.exit_code == 0

        # Modify datasets.xml
        source_test_xml = local_repo_path / "tests/data/datasets.d/dataset1.xml"
        file = source_test_xml.read_text()
        file = file.replace('datasetID="dataset1"', 'datasetID="dataset1-modified"')
        file = file.replace(
            '<att name="title">title</att>', '<att name="title">title-modified</att>'
        )
        (source_test_xml.parent / (source_test_xml.stem + "-modidied.xml")).write_text(
            file
        )

        # Sync with hard flag
        result = run_cli(
            *initial_args,
            "--hard-flag",
            "--hard-flag-dir",
            hard_flag_dir,
        )
        assert result.exit_code == 0
        assert (hard_flag_dir / "dataset1-modified").exists()


class TestErddapDeploySave:
    def test_save(self, tmp_path):
        result = run_cli("save", "--output", f"{tmp_path}/datasets.xml")
        assert result.exit_code == 0

    def test_save_help(self):
        result = run_cli("save", "--help")
        assert result.exit_code == 0
