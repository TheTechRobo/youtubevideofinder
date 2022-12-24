from flask import Flask, render_template, request

import lostmediafinder

app = Flask(__name__)

@app.route("/find/<id>")
async def youtubev2(id):
    """
    Provides backwards compatibility for the old endpoint.
    """
    return (await lostmediafinder.YouTubeResponse.generateAsync(id)).coerce_to_api_version(2).json()

async def wrapperYT(id):
    """
    Wrapper for generateAsync
    """
    return await lostmediafinder.YouTubeResponse.generateAsync(id)

@app.route("/api/v<int:v>/<site>/<id>")
@app.route("/api/v<int:v>/<id>")
async def youtube(v, id, site="youtube"):
    """
    Wrapper around lostmediafinder
    """
    if v == 1:
        return "This API version is no longer supported.", 410
    if v not in (2, 3):
        return "Unrecognised API version", 404
    if site == "youtube":
        return (await wrapperYT(id)).coerce_to_api_version(v).json()
    return "Unrecognised site", 404

@app.route("/")
async def index():
    """
    Shows the landing page
    """
    default = request.args.get("q") or ""
    return render_template("init.html", default=default)

def parse_changelog(changelog):
    """
    Parses a changelog out of a lostmediafinder docstring
    """
    parsed = {}
    for i in changelog.split("API VERSION "):
        restOfLine = i.split("\n")[0]
        others = i.split("\n")[1:]
        parsed[restOfLine] = others
    return parsed

@app.route("/api")
async def api():
    """
    API docs
    """
    responseDocstring = lostmediafinder.YouTubeResponse.__doc__
    serviceDocstring = lostmediafinder.Service.__doc__
    changelog = [{}, {}]
    rChangelog = responseDocstring.split("=Changelog=")
    sChangelog = serviceDocstring.split("=Changelog=")
    responseDocstring = rChangelog[0]
    serviceDocstring = sChangelog[0]
    if len(rChangelog) > 1:
        changelog[0] = parse_changelog(rChangelog[1].strip())
    if len(sChangelog) > 1:
        changelog[1] = parse_changelog(sChangelog[1].strip())
    # TODO: Parse that
    # This works fine for now tho
    return render_template("api.html", fields=responseDocstring, services=serviceDocstring, changelog=changelog)
