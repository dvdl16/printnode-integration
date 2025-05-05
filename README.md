## Printnode Integration

[![CI workflow](https://github.com/dvdl16/printnode-integration/actions/workflows/ci.yml/badge.svg?branch=version-15)](https://github.com/dvdl16/printnode-integration/actions/workflows/ci.yml)

< codecov badge here >

Integration with Printnode API

#### License

MIT

### Features

1. Print from the UI on any Document
2. Set up automatic printing based on Document Events


### User documentation

TBC

### Development


#### Installation

To install the PrintNode Python library in editable mode:

```bash
cd frappe-bench
./env/bin/pip install -e git+https://github.com/PrintNode/PrintNode-Python.git#egg=printnodeapi
```


#### Tests

To run unit tests:

```shell
bench --site test_site run-tests --app printnode_integration --coverage
```

To run UI/integration tests:

The following depencies are required
```shell
sudo apt update
# Dependencies for cypress: https://docs.cypress.io/guides/continuous-integration/introduction#UbuntuDebian
sudo apt-get install libgtk2.0-0 libgtk-3-0 libgbm-dev libnotify-dev libgconf-2-4 libnss3 libxss1 libasound2 libxtst6 xauth xvfb

sudo apt-get install chromium
```

```shell
bench --site test_site run-ui-tests printnode_integration --headless --browser chromium
```

#### Contributing

We use [pre-commit](https://pre-commit.com/) for linting. First time setup may be required:
```shell
# Install pre-commit
pip install pre-commit

# Install the git hook scripts
pre-commit install

#(optional) Run against all the files
pre-commit run --all-files
```

We use [Semgrep](https://semgrep.dev/docs/getting-started/) rules specific to [Frappe Framework](https://github.com/frappe/frappe)
```shell
# Install semgrep
python3 -m pip install semgrep

# Clone the rules repository
git clone --depth 1 https://github.com/frappe/semgrep-rules.git frappe-semgrep-rules

# Run semgrep specifying rules folder as config 
semgrep --config=/workspace/development/frappe-semgrep-rules/rules apps/printnode_integration
```


The documentation has been generated using [mdBook](https://rust-lang.github.io/mdBook/guide/creating.html)

Make sure you have [mdbook](https://rust-lang.github.io/mdBook/guide/installation.html) installed/downloaded. To modify and test locally:
```shell
cd docs
mdbook serve --open
```
