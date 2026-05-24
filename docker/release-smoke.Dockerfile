FROM python:3.11-slim

ARG WHEEL=dist/mofumofu-0.1.0-py3-none-any.whl

WORKDIR /smoke
COPY ${WHEEL} /tmp/mofumofu.whl

RUN apt-get update && apt-get install -y --no-install-recommends nodejs npm && rm -rf /var/lib/apt/lists/*
RUN python -m pip install --no-cache-dir /tmp/mofumofu.whl
RUN mofu --version
RUN mofu agent --help
RUN python -m mofu --version
RUN mkdir /tmp/project && cd /tmp/project && mofu init --json && mofu status --json && mofu provider list --json
RUN python -m pip uninstall -y mofumofu
