
# ERDDAP Checks

`erddap-checks` run a series of tests on the different ERDDAP components to make sure a deployment will deploy successfully.

## Gitub Action

Add the following step to your GitHub Action.

```yaml
      - name: Run erddap-checks
        uses: hakaiinstitute/erddap-checks@main
        with:
            datasets_xml: "optional path to datasets.xml or datasets.d/*.xml"
```

We also recommend running an XML linter to detect XML-specific issues. SuperLinter is great for this!

```yaml
      - name: Lint Code Base
        uses: github/super-linter/slim@v4
        env:
          VALIDATE_ALL_CODEBASE: false
          DEFAULT_BRANCH: main
          VALIDATE_XML: true
          LOG_LEVEL: WARN
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

## Local testing

Install the package:

```console
pip install git+https://github.com/HakaiInstitute/erddap-checks.git
```

Run checks:

```console
erddap_checks "path to dataset.xml"
```

For options:

```console
erddap_checks --help
```
