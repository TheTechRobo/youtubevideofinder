# lostmediafinder
Currently YouTube is the only supported site, but that might change.

Contributions are welcome!

## CLI tool
Currently no documentation exists for the CLI tool.

## Usage as a module
There are docstrings included in the module (it is contained in `lostmediafinder`), but no `setup.py` or PyPI package is currently included. This is because it is not yet 100% stable (and I plan on adding support for more websites soon).

## Frontend
### Running in Docker (recommended):
There is an included Dockerfile. I will figure out publishing to Docker Hub soon enough.

Instead of modiying the Hypercorn config, use `HYPERCORN_<VARIABLE_NAME>` environment variables; the config is setup to work with that.

A command like this should work (runs on port 8000; change the `-p` flag to `<whatever port you want>:8000` to change that):

```
docker run --restart=unless-stopped -p 8000:8000 -e GUNICORN_WORKERS=4 thetechrobo/findyoutubevideo
```

### Running outside of Docker (unsupported)
You should be able to check the Dockerfile for what it is doing during the build (it's a glorified shell script).

## Configuration

`config.template.yml` has an example.

First, set the `User-Agent` globally in your `config.yml` file. Note that it isn't currently used for all scrapers as some require mimicking a browser.

### Example `config.yml`

```yaml
version:

# Global User-Agent
user_agent: "FindYoutubeVideo/1.0 operated by TheTechRobo"

methods:
  youtube:
    title: YouTube
    enabled: true
...
```

## Licence

Copyright (c) 2022-2024 TheTechRobo

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.

You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
