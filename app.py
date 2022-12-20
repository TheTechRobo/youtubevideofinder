import re
import lostmediafinder

from flask import Flask, render_template, request, abort

app = Flask(__name__)

@app.route("/find/<id>")
async def youtubev2(id):
    return (await lostmediafinder.YouTubeResponse.generateAsync(id)).json()

async def wrapperYT(id):
    return await lostmediafinder.YouTubeResponse.generateAsync(id)

@app.route("/api/v<int:v>/<site>/<id>")
@app.route("/api/v<int:v>/<id>")
async def youtube(v, id, site="youtube"):
    if v == 1:
        return "This API version is no longer supported.", 410
    if v not in (2, 3):
        return "Unrecognised API version", 404
    if site == "youtube":
        return (await wrapperYT(id)).coerce_to_api_version(v).json()
    return "Unrecognised site", 404

@app.route("/")
async def index():
    return render_template("init.html")

def parseChangelog(changelog):
    parsed = {}
    for i in changelog.split("API VERSION "):
        restOfLine = i.split("\n")[0]
        others = i.split("\n")[1:]
        parsed[restOfLine] = others
    return parsed

@app.route("/api")
async def api():
    responseDocstring = lostmediafinder.YouTubeResponse.__doc__
    serviceDocstring = lostmediafinder.Service.__doc__
    changelog = [{}, {}]
    rChangelog = responseDocstring.split("=Changelog=")
    sChangelog = serviceDocstring.split("=Changelog=")
    responseDocstring = rChangelog[0]
    serviceDocstring = sChangelog[0]
    if len(rChangelog) > 1:
        changelog[0] = parseChangelog(rChangelog[1].strip())
    if len(sChangelog) > 1:
        changelog[1] = parseChangelog(sChangelog[1].strip())
    # TODO: Parse that
    # This works fine for now tho
    return render_template("api.html", fields=responseDocstring, services=serviceDocstring, changelog=changelog)
