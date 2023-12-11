FROM python:3.10-slim-bullseye
RUN pip install --no-cache-dir gunicorn flask[async]
RUN apt install -y openssl

EXPOSE 8000
RUN pip install -r REQUIREMENTS.txt
COPY . /app
WORKDIR /app
ENTRYPOINT ["gunicorn", "-b", "0.0.0.0:8000", "--config", "gunicorn.conf", "app:app"]
