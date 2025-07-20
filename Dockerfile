FROM python:3.11-slim-bullseye
RUN pip install --no-cache-dir hypercorn quart
RUN apt install -y openssl
RUN apt clean
# The following line does not necessarily have to be updated with the requirements.txt as this is just to speed up the requirements.txt part (to improve cachability)
RUN pip install --no-cache-dir snscrape==0.4.3.20220106 aiohttp[speedups] requests nest_asyncio cachetools click asyncache pyyaml

EXPOSE 8000
COPY . /app
WORKDIR /app
RUN pip install --upgrade -r REQUIREMENTS.txt
ENTRYPOINT ["hypercorn", "-b", "0.0.0.0:8000", "--config", "file:hypercorn_conf.py", "app:app"]
