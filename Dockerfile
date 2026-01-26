FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install build deps for optional libraries (Pillow may need libjpeg)
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libjpeg-dev zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN python -m pip install --upgrade pip setuptools wheel \
    && pip install -r requirements.txt

COPY . /app

EXPOSE 5000

ENTRYPOINT ["waitress-serve", "--listen=0.0.0.0:5000", "app:app"]
