# Convert environment variables to configuration
# e.g. HYPERCORN_WORKERS=4
# The HYPERCORN_  must be capatalised

import os

for k,v in os.environ.items():
    if k.startswith("HYPERCORN_"):
        key = k.split('_', 1)[1].lower()
        locals()[key] = v

