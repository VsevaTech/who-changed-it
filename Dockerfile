# Base image is overridable so the build can be reproduced from a mirror
# (e.g. --build-arg BASE_IMAGE=my-registry/python:3.12-slim).
ARG BASE_IMAGE=python:3.12-slim
FROM ${BASE_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore

WORKDIR /srv

COPY pyproject.toml README.md ./
COPY app ./app
COPY examples ./examples
RUN python -m pip install --no-cache-dir . \
 && useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin wci \
 && chown -R wci:wci /srv

USER wci
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2).status == 200 else 1)"

# --no-access-log: request lines are not needed and must never carry payload data.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
