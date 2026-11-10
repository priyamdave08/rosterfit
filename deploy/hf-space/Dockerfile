# Hugging Face Space (Docker SDK) for the RosterFit API.
# Installs RosterFit at a pinned commit with the dashboard's pinned dependencies (the versions the
# bundled models were trained with), then serves FastAPI on the port Spaces expects.
FROM python:3.12-slim

ARG ROSTERFIT_REF=main
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user PATH=/home/user/.local/bin:$PATH PYTHONUNBUFFERED=1
WORKDIR /home/user/app

RUN git clone --depth 1 --branch "${ROSTERFIT_REF}" https://github.com/priyamdave08/rosterfit.git . \
 && pip install --no-cache-dir --user -r requirements.txt "fastapi==0.162.2" "uvicorn[standard]==0.54.0"

EXPOSE 7860
CMD ["uvicorn", "rosterfit.api.main:app", "--host", "0.0.0.0", "--port", "7860"]
