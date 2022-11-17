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
    responseDocstring = lostmediafinder.Response.__doc__
    serviceDocstring = lostmediafinder.Service.__doc__
    # TODO: Parse that
    # This works fine for now tho
    return render_template("api.html", fields=responseDocstring, services=serviceDocstring, type=type)

@app.route("/nojs")
async def formsubmit():
    vid = request.args.get("vid") or abort(400)
    return render_template("fid.html", data=(await find(vid)), vid=vid, nonoscript=True)

@app.route("/ui/fid")
async def fid():
    vid = request.args.get("vid") or abort(400)
    return render_template("fid.html", data=find(vid), vid=vid)
