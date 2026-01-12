# La Metro Translation Suite

_A shiny new Wagtail project!_

## Development

### Setup

#### Docker

Development requires a local installation of [Docker](https://docs.docker.com/install/)
and [Docker Compose](https://docs.docker.com/compose/install/).

#### Pre-commit

Pre-commit hooks are scripts that run on your local machine before every commit.

We use the [pre-commit](https://pre-commit.com/) framework to run code linters and formatters that keep our codebase clean.

To set up Pre-Commit, install the Python package on your local machine using:

```bash
python -m pip install pre-commit
```

If you'd rather not install pre-commit globally, create and activate a [virtual environment](https://docs.python.org/3/library/venv.html) in this repo before running the above command.

Then, run:

```bash
pre-commit install
```

Since hooks are run locally, you can modify which scripts are run before each commit by modifying `.pre-commit-config.yaml`.

### Usage

#### Running the app

```bash
docker compose up
```

#### Running the tests

```bash
docker compose -f docker-compose.yml -f tests/docker-compose.yml run --rm app
```

#### Managing site styles

We use the Bootstrap Node package to build a custom version of Bootstrap for our use. To
make changes to Bootstrap defaults (colors, layout, etc.), update the included Sass file
at `la_metro_translation_suite/static/scss/la_metro_translation_suite.scss`. Changes
to this file will automatically be applied during local development.

To add styles unrelated to Bootstrap, e.g., customizing a map or some other novel element,
update the included CSS file at `la_metro_translation_suite/static/css/la_metro_translation_suite.css`.

#### Managing CMS content

Initial CMS content is loaded in a data migration using the `initialize_database` management
command.

You will need to create a default user in order to access the CMS:

```bash
python manage.py createsuperuser
```

To dump your local database to a fixture and copy any files you've uploaded locally, run:

```bash
docker compose run --rm app python manage.py dump_content
```

To load a fixture into your local database, run:

```bash
docker compose run --rm app python manage.py load_content
```
