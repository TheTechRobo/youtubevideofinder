import re
import lostmediafinder

from flask import Flask, render_template, request, abort

app = Flask(__name__)

@app.route("/find/<id>")
async def youtube(id):
    if not re.match(r"^[A-Za-z0-9_-]{10}[AEIMQUYcgkosw048]$", id):
        return {"status": "bad.id", "true": True, "id": None}, 400
    return (await lostmediafinder.YouTubeResponse.generateAsync(id)).json()

@app.route("/api/v<int:v>/<site>/<id>")
@app.route("/api/v<int:v>/<id>")
async def findapi(v, id, site="query"):
    if v == 1:
        return "This API version is no longer supported.", 410
    if v != 2:
        return "Unrecognised API version", 404
    if site == "query":
        site = request.args.get("site") or abort(400)
    if site == "youtube":
        return await youtube(id)
    return "Unrecognised site", 404

@app.route("/")
async def index():
    return render_template("init.html")

@app.route("/api")
async def api():
    responseDocstring = lostmediafinder.YouTubeResponse.__doc__
    serviceDocstring = lostmediafinder.Service.__doc__
    # TODO: Parse that
    # This works fine for now tho
    return render_template("api.html", fields=responseDocstring, services=serviceDocstring, type=type)
