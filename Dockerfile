FROM python:3.11-slim-bullseye
RUN pip install --no-cache-dir hypercorn quart
RUN apt install -y openssl
RUN apt clean
# The following line just improves cachability. It doesn't necessarily have to be kept up to date with requirements.txt.
RUN pip install --no-cache-dir snscrape==0.4.3.20220106 aiohttp[speedups] requests click pyyaml

EXPOSE 8000
COPY . /app
WORKDIR /app
RUN pip install --upgrade -r REQUIREMENTS.txt
ENTRYPOINT ["hypercorn", "-b", "0.0.0.0:8000", "--config", "file:hypercorn_conf.py", "app:app"]
