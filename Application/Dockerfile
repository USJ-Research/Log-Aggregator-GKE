FROM python:3.13.3-bookworm

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["sh", "-c", "\
    python manage.py makemigrations --noinput --verbosity 0 && \
    python manage.py migrate --noinput --verbosity 0 && \
    gunicorn simply.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 3 \
    --worker-class gthread \
    --threads 4 \
    --timeout 30 \
    --error-logfile /app/gunicorn-error.log \
"]