import re

from flask import *
from findmedia import *

app = Flask(__name__)

try:
    config.ccen
except AttributeError:
    config.ccen = False
    config.ccod = "a"

#@app.route(f"/cc/{config.ccod}")
async def cc():
    global GCACHE, FILCACHE, YACACHE, WBMCACHE, IACACHE
    GCACHE = {}
    FILCACHE = {}
    YACACHE = {}
    WBMCACHE = {}
    IACACHE = {}
    abort(404)


@app.route("/find/<id>")
async def find(id):
    if not re.match(r"^[A-Za-z0-9_-]{10}[AEIMQUYcgkosw048]$", id):
        return {"status": "bad.id", "true": True, "id": None}, 400
    return {
            "status": "find.id",
            "true": True,
            "id": id,
            "ya": yairc(id),
            "wbm": wbm(id),
            "ia": iai(id),
            "filmot": filmot(id),
            "ghostarchive": ghostget(id),
            "keys": ["wbm", "ia", "ghostarchive", "ya", "filmot"]
    }

@app.route("/")
async def ui():
    return render_template("init.html")

@app.route("/api")
async def api():
    return render_template("api.html", fields={"id": "The interpreted video ID.", "status": "bad.id if invalid ID.", "keys": "Array of all the service keys."}, services={"archived": "Whether the video is archived or not.", "available": "A link to the archived material if it can be produced; False otherwise.", "capcount": "The number of captures. Currently deprecated - the capture count sent may or may not be the true number of captures. However, it will always be a positive non-zero number if the video is archived.", "lastupdated": "The timestamp the data was retrieved from the server. Used internally to expire cache entries.", "name": "The name of the service. Used in the UI.", "note": "A footnote about the service. This could be different depending on conditions. For example, the Internet Archive has an extra passage if the item is dark.", "rawraw": "The data used to check whether the video is archived on that particular service. For example, for GhostArchive, it would be the HTTP status code.", "suppl": "Supplemental error message. Not used and currently inconsistent with what it returns and when."})

@app.route("/nojs")
async def formsubmit():
    vid = request.args.get("vid") or abort(400)
    return render_template("fid.html", data=(await find(vid)), vid=vid, nonoscript=True)

@app.route("/ui/fid")
async def fid():
    vid = request.args.get("vid") or abort(400)
    return render_template("fid.html", data=find(vid), vid=vid)
