from flask import Flask, render_template, request, Response, redirect

import re, urllib.parse

import lostmediafinder

app = Flask(__name__)

@app.route("/robots.txt")
async def robots():
    return """
# I'm 100% fine with crawlers, just don't fuck up my servers.
User-Agent: *
Crawl-delay: 2
Disallow:
    """.strip()

@app.route("/find/<id>")
async def youtubev2(id):
    """
    Provides backwards compatibility for the old endpoint.
    """
    return (await lostmediafinder.YouTubeResponse.generate(id)).coerce_to_api_version(2).json()

async def wrapperYT(id):
    """
    Wrapper for generateAsync
    """
    return await lostmediafinder.YouTubeResponse.generate(id)

@app.route("/api/v<int:v>/<site>/<id>")
@app.route("/api/v<int:v>/<id>")
async def youtube(v, id, site="youtube", json=True):
    """
    Wrapper around lostmediafinder
    """
    if v == 1:
        return "This API version is no longer supported.", 410
    if v not in (2, 3):
        return "Unrecognised API version", 404
    if site == "youtube":
        r = (await wrapperYT(id)).coerce_to_api_version(v)
        if json:
            return r.json()
        return r
    return "Unrecognised site", 404

@app.route("/noscript_init.html")
async def noscript_init():
    if id := request.args.get("d"):
        return redirect("/noscript_load.html?d=" + id)
    return """
    <!DOCTYPE html>
    <html>
      <body style="text-align:center;align-items:center">
        <p>Awaiting input...</p>
      </body>
    </html>
    """

ID_PATTERN = re.compile(r'^[A-Za-z0-9_-]{10}[AEIMQUYcgkosw048]$')
PATTERNS = [
    re.compile(r'(?:https?://)?(?:\w+\.)?youtube\.com/watch/?\?v=([A-Za-z0-9_-]{10}[AEIMQUYcgkosw048])(?:[\/&].*)?', re.IGNORECASE),
    re.compile(r'(?:https?://)?(?:\w+\.)?youtube.com/(?:v|embed|shorts|video)/([A-Za-z0-9_-]{10}[AEIMQUYcgkosw048])(?:[\/&].*)?', re.IGNORECASE),
    re.compile(r'(?:https?://)?youtu.be/([A-Za-z0-9_-]{10}[AEIMQUYcgkosw048])(?:\?.*)?', re.IGNORECASE),
    re.compile(r'(?:https?://)?filmot.com/video/([A-Za-z0-9_-]{10}[AEIMQUYcgkosw048])(?:\?.*)?', re.IGNORECASE)
]

def coerce_to_id(vid):
    if re.match(ID_PATTERN, vid):
        return vid

    for pattern in PATTERNS:
        newVid = re.sub(pattern, lambda match: match.group(1), vid)
        if re.match(ID_PATTERN, newVid):
            return newVid
    return None

@app.route("/noscript_load.html")
async def noscript_load():
    if not request.args.get("d"):
        return "No d param provided - It should be the video id or url", 400
    id = coerce_to_id(request.args['d'])
    if not id:
        return """
        <!DOCTYPE html>
        <html><body style="text-align:center;align-items:center;">
          <p style="color:red">Could not parse your input as a video ID or URL.<br />Your input was:<br /><code>%s</code></p>
          <br />IF the video ID or URL is valid, please file an issue on github!
        </body></html>
        """ % request.args['d'], 400
    response = Response("""
    <!DOCTYPE html>
    <html>
    <head><meta http-equiv="refresh" content="0; url=/noscript_load_thing.html?id=%s" /></head>
    <body>
    <img src="/static/ab79a231234507.564a1d23814ef.gif" width="25" height="25" />Loading could take up to 45 seconds.</img>
    </body>
    </html>
    """ % id, headers=(("FinUrl", f"/noscript_load_thing.html?id={id}"),))
    return response, 302

@app.route("/noscript_load_thing.html")
async def load_thing():
    if not request.args.get("id"):
        return "Missing id parameter", 400
    t = await youtube(3, request.args['id'], "youtube", json=False)
    return render_template("fid.html", resp=t)

@app.route("/")
async def index():
    """
    Shows the landing page
    """
    default = request.args.get("q") or ""
    default_id = coerce_to_id(default) or ""
    return render_template("init.html", default=default,default_id=default_id)

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

class E:
    """
    What does this do? Good question
    """
    name: str
    type: str

    def __init__(self, name, type):
        name = name.strip()
        type = type.strip()

        self.name = name
        self.type = type
        self.type = self.type.rstrip(")")

async def parse_lines(lines: list[str]) -> dict[E, str]:
    """
    Parses lines into a mapping
    """
    r = {}
    for line in lines:
        line = line.strip()
        splitted = line.split(":", 1)
        field = E(*splitted[0].split(" ("))
        description = splitted[1].strip()
        r[field] = description
    return r

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
    # Parse the attributes list
    responseDocstring = await parse_lines(rChangelog[0].split("Attributes:\n")[1].strip().split("\n"))
    serviceDocstring  = await parse_lines(sChangelog[0].split("Attributes:\n")[1].strip().split("\n"))
    return render_template("api.html", fields=responseDocstring, services=serviceDocstring, changelog=changelog)
