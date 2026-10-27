# Build FastAPI App
FROM python:3.11-slim

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Dependencies first, so Cloud Build reuses these layers until requirements.txt changes.
COPY ./requirements.txt .
RUN pip install --upgrade pip setuptools wheel \
    && pip install "uvicorn[standard]" gunicorn \
    && pip install -r requirements.txt

COPY . .

# Run Gunicorn with appropriate workers and threads
CMD exec gunicorn --bind :$PORT --workers 4 --threads 8 --worker-class uvicorn.workers.UvicornWorker 'main:app'
