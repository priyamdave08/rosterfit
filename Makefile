PY ?= .venv/bin/python

.PHONY: install data db train all app api test lint docker synth

install:          ## create venv and install everything
	uv venv --python 3.12 .venv && uv pip install --python $(PY) -e ".[dev,aws,api,train]"

data:             ## pull Basketball-Reference, Torvik and ESPN (cached, rate-limited)
	$(PY) -m rosterfit.cli ingest

db:               ## build DuckDB staging views + marts
	$(PY) -m rosterfit.cli build-db

train:            ## archetypes, lineup model, prospect model (logged to MLflow)
	$(PY) -m rosterfit.cli train

all: data db train

app:              ## Streamlit front-office dashboard on :8501
	.venv/bin/streamlit run src/rosterfit/app/streamlit_app.py

api:              ## FastAPI on :8000 (docs at /docs)
	.venv/bin/uvicorn rosterfit.api.main:app --reload

mlflow:           ## browse experiment runs
	.venv/bin/mlflow ui --backend-store-uri sqlite:///data/mlflow.db

test:
	$(PY) -m pytest -q

lint:
	.venv/bin/ruff check src tests

docker:
	docker build -t rosterfit .

synth:            ## render the AWS CloudFormation template (no AWS calls)
	cd infra && npx --yes aws-cdk@2 synth --app "../$(PY) app.py" > /dev/null && echo "synth OK"
