# lostmediafinder

Currently YouTube is the only supported site, but that might change.

Contributions are welcome!

## CLI tool
Currently no documentation exists for the CLI tool.

## Usage as a module
There are docstrings included in the module (it is contained in `lostmediafinder`), but no `setup.py` or PyPI package is currently included. This is because it is not yet 100% stable (and I plan on adding support for more websites soon).

## Frontend
### Running in Docker(recommended):
The software is available on Docker Hub: <https://hub.docker.com/r/thetechrobo/findyoutubevideo> Let me know if it doesn't work or if you need help.

Instead of modiying the gunicorn config, use `GUNICORN_<VARIABLE_NAME>` environment variables; the config is setup to work with that. For example, `GUNICORN_WORKERS` is the number of threads that are spawned to handle requests.

A command like this should work (runs on port 8000; change the `-p` flag to `<whatever port you want>:8000` to change that):

```
docker run --restart=unless-stopped -p 8000:8000 -e GUNICORN_WORKERS=4 thetechrobo/findyoutubevideo
```

## Licence

Copyright (c) 2022-2024 TheTechRobo

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.

You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0
