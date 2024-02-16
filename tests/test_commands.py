from pathlib import Path

from click.testing import CliRunner

from erddap_deploy.cli import cli

TEST_REPO = "https://github.com/HakaiInstitute/erddap-deploy.git"


def convert_env(env):
    return {key.replace("ERDDAP_", ""): value for key, value in env.items()}


def run_cli(*args, env=None):
    runner = CliRunner()
    return runner.invoke(cli, args, env=env, catch_exceptions=False)


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
        local_repo_path = tmp_path / "datasets-repo"
        result = run_cli(
            "--datasets-xml",
            local_repo_path / "**/datasets.d/*.xml",
            "--active-datasets-xml",
            active_datasets_xml,
            "sync",
            "--repo-url",
            TEST_REPO,
            "--branch",
            "main",
            "--local-repo-path",
            local_repo_path,
            "--pull",
        )
        assert result.exit_code == 0, result.output

    def test_sync_help(self):
        result = run_cli("sync", "--help")
        assert result.exit_code == 0

    def test_sync_hard_flag(self, tmp_path):
        env = {"ERDDAP_bigParentDirectory": "erddapData"}
        active_datasets_xml = tmp_path / "datasets.xml"
        local_repo_path = tmp_path / "datasets-repo"
        hard_flag_dir = tmp_path / "{bigParentDirectory}/hardFlag"

        formated_hard_flag_dir = Path(str(hard_flag_dir).format(**convert_env(env)))
        formated_hard_flag_dir.mkdir(parents=True)

        # iniatialize datasets.xml
        initial_args = (
            "--datasets-xml",
            local_repo_path / "**/datasets.d/*.xml",
            "--active-datasets-xml",
            active_datasets_xml,
            "sync",
            "--repo-url",
            TEST_REPO,
            "--branch",
            "main",
            "--local-repo-path",
            local_repo_path,
        )
        result = run_cli(
            *initial_args,
        )
        assert result.exit_code == 0, result.output

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
        assert (formated_hard_flag_dir / "dataset1-modified").exists()


class TestErddapDeploySave:
    def test_save(self, tmp_path):
        result = run_cli("save", "--output", f"{tmp_path}/datasets.xml")
        assert result.exit_code == 0

    def test_save_help(self):
        result = run_cli("save", "--help")
        assert result.exit_code == 0

    def test_save_secrets(self, tmp_path):
        output_dataset_xml = tmp_path / "datasets.xml"
        result = run_cli(
            '--secrets={"TEST_SECRET": "TEST_VALUE"}',
            "save",
            "--output",
            output_dataset_xml,
        )
        assert result.exit_code == 0
        output_dataset_xml_content = output_dataset_xml.read_text()
        assert output_dataset_xml.exists()
        assert output_dataset_xml_content
        assert "TEST_VALUE" in output_dataset_xml_content
        assert "TEST_SECRET" not in output_dataset_xml_content

    def test_save_env_secrets(self, tmp_path):
        output_dataset_xml = tmp_path / "datasets.xml"
        result = run_cli(
            "save",
            "--output",
            output_dataset_xml,
            env={"ERDDAP_SECRET_TEST_SECRET": "TEST_VALUE"},
        )
        assert result.exit_code == 0
        output_dataset_xml_content = output_dataset_xml.read_text()
        assert output_dataset_xml.exists()
        assert output_dataset_xml_content
        assert "TEST_VALUE" in output_dataset_xml_content
        assert "TEST_SECRET" not in output_dataset_xml_content
        assert "ERDDAP_SECRET_TEST_SECRET" not in output_dataset_xml_content

    def test_save_with_erddap_secret_env_variable(self, tmp_path):
        output_dataset_xml = tmp_path / "datasets.xml"
        result = run_cli(
            "save",
            "--output",
            output_dataset_xml,
            env={"ERDDAP_SECRETS": '{"TEST_SECRET": "TEST_VALUE"}'},
        )
        assert result.exit_code == 0
        output_dataset_xml_content = output_dataset_xml.read_text()
        assert output_dataset_xml.exists()
        assert output_dataset_xml_content
        assert "TEST_VALUE" in output_dataset_xml_content
        assert "TEST_SECRET" not in output_dataset_xml_content
        assert "ERDDAP_SECRETS" not in output_dataset_xml_content

    def test_save_secrets_input_prevail_env_variables(self, tmp_path):
        output_dataset_xml = tmp_path / "datasets.xml"
        result = run_cli(
            '--secrets={"TEST_SECRET": "TEST_VALUE"}',
            "save",
            "--output",
            output_dataset_xml,
            env={"ERDDAP_SECRET_TEST_SECRET": "TEST_VALUE_ENV"},
        )
        assert result.exit_code == 0
        output_dataset_xml_content = output_dataset_xml.read_text()
        assert output_dataset_xml.exists()
        assert output_dataset_xml_content
        assert "TEST_VALUE" in output_dataset_xml_content
        assert "TEST_SECRET" not in output_dataset_xml_content
        assert "TEST_VALUE_ENV" not in output_dataset_xml_content
        assert "ERDDAP_SECRET_TEST_SECRET" not in output_dataset_xml_content
