# Convert environment variables to configuration
# e.g. GUNICORN_WORKERS=4
# The GUNICORN_  must be capatalised

import os

for k,v in os.environ.items():
    if k.startswith("GUNICORN_"):
        key = k.split('_', 1)[1].lower()
        locals()[key] = v

