FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements/base.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY . /app
RUN python manage.py collectstatic --noinput
RUN chmod +x /app/start.sh /app/build.sh
RUN useradd --create-home app && chown -R app:app /app
USER app
CMD ["./start.sh"]
