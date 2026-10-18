FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencies first: this layer is cached until requirements.txt changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# settings.py needs these at import; dummy values, real ones come from .env at runtime
RUN DJANGO_SECRET_KEY=collectstatic DEVICE_USERNAME=x DEVICE_PASSWORD=x \
    python manage.py collectstatic --noinput

# Same UID as the host user, so files in the ./data bind mount stay writable
RUN useradd --uid 1000 app && chown app /app/data
USER app

EXPOSE 8000

# One worker: device locks live in process memory
CMD ["gunicorn", "config.wsgi", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "4", "--access-logfile", "-", "--no-control-socket"]
