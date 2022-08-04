import re

from flask import *
from findmedia import *

app = Flask(__name__)

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

@app.route("/nojs")
async def formsubmit():
    vid = request.args.get("vid") or abort(400)
    return render_template("fid.html", data=(await find(vid)), vid=vid, nonoscript=True)

@app.route("/ui/fid")
async def fid():
    vid = request.args.get("vid") or abort(400)
    return render_template("fid.html", data=find(vid), vid=vid)
