import re
import lostmediafinder

from flask import *

app = Flask(__name__)

@app.route("/find/<id>")
async def find(id):
    if not re.match(r"^[A-Za-z0-9_-]{10}[AEIMQUYcgkosw048]$", id):
        return {"status": "bad.id", "true": True, "id": None}, 400
    return (await lostmediafinder.Response.generateAsync(id)).json()

@app.route("/")
async def ui():
    return render_template("init.html")

@app.route("/api")
async def api():
    return render_template("api.html", fields={"id": "The interpreted video ID.", "status": "bad.id if invalid ID.", "keys": "Array of all the service keys."}, services={"archived": "Whether the video is archived or not.", "available": "A link to the archived material if it can be produced; False otherwise.", "capcount": "The number of captures. Currently deprecated - the capture count sent may or may not be the true number of captures. However, it will always be a positive non-zero number if the video is archived.", "lastupdated": "The timestamp the data was retrieved from the server. Used internally to expire cache entries.", "name": "The name of the service. Used in the UI.", "note": "A footnote about the service. This could be different depending on conditions. For example, the Internet Archive has an extra passage if the item is dark.", "rawraw": "The data used to check whether the video is archived on that particular service. For example, for GhostArchive, it would be the HTTP status code.", "suppl": "Supplemental error message. Not used and currently inconsistent with what it returns and when.", "metaonly": "True if only the metadata is archived. This value should not be relied on!", "comments": "True if the comments are archived. This value should not be relied on!"})

@app.route("/nojs")
async def formsubmit():
    vid = request.args.get("vid") or abort(400)
    return render_template("fid.html", data=(await find(vid)), vid=vid, nonoscript=True)

@app.route("/ui/fid")
async def fid():
    vid = request.args.get("vid") or abort(400)
    return render_template("fid.html", data=find(vid), vid=vid)
