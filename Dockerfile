FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements/base.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY . /app
RUN useradd --create-home app && chown -R app:app /app
USER app
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "config.asgi:application"]
