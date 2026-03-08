# Build FastAPI App
FROM python:3.11-slim

WORKDIR /app


COPY ./requirements.txt .
RUN pip install --upgrade pip setuptools wheel
RUN pip install "uvicorn[standard]" gunicorn
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run Gunicorn with appropriate workers and threads
CMD exec gunicorn --bind :$PORT --workers 4 --threads 8 --worker-class uvicorn.workers.UvicornWorker 'main:app'
