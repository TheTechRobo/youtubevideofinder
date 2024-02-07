from flask import Flask, render_template, request, Response, redirect, send_from_directory
import re, urllib.parse, yaml, json
import lostmediafinder

app = Flask(__name__)

with open('config.yml', 'r') as file:
    config_yml = yaml.safe_load(file)

@app.route("/robots.txt")
async def robots():
    return send_from_directory("static", "robots.txt")

@app.route("/find/<id>")
async def youtubev2(id):
    """
    Provides backwards compatibility for the old endpoint.
    """
    return (await lostmediafinder.YouTubeResponse.generate(id)).coerce_to_api_version(2).json()

async def wrapperYT(id, includeRaw):
    """
    Wrapper for generateAsync
    """
    return await lostmediafinder.YouTubeResponse.generate(id, includeRaw)

@app.route("/api/v<int:v>/<site>/<id>")
@app.route("/api/v<int:v>/<id>")
async def youtube(v, id, site="youtube", json=True):
    """
    Wrapper around lostmediafinder
    """
    includeRaw = True
    if v == 1:
        return "This API version is no longer supported.", 410
    if v not in (2, 3, 4):
        return "Unrecognised API version", 404
    if site == "youtube":
        includeRaw = True
        if v >= 4:
            # Versions 4 and higher only provide `rawraw` if you ask for it
            includeRaw = "includeRaw" in request.args
        r = (await wrapperYT(id, includeRaw=includeRaw)).coerce_to_api_version(v)
        if json:
            return r.json()
        return r
    return "Unrecognised site", 404

@app.route("/noscript_init.html")
async def noscript_init():
    if id := request.args.get("d"):
        return redirect("/noscript_load.html?d=" + id)
    return render_template("noscript/init.j2")

ID_PATTERN = re.compile(r'^[A-Za-z0-9_-]{10}[AEIMQUYcgkosw048]$')
PATTERNS = [
    re.compile(r'(?:https?://)?(?:\w+\.)?youtube\.com/watch/?\?v=([A-Za-z0-9_-]{10}[AEIMQUYcgkosw048])(?:[\/&].*)?', re.IGNORECASE),
    re.compile(r'(?:https?://)?(?:\w+\.)?youtube.com/(?:v|embed|shorts|video)/([A-Za-z0-9_-]{10}[AEIMQUYcgkosw048])(?:[\/&].*)?', re.IGNORECASE),
    re.compile(r'(?:https?://)?youtu.be/([A-Za-z0-9_-]{10}[AEIMQUYcgkosw048])(?:\?.*)?', re.IGNORECASE),
    re.compile(r'(?:https?://)?filmot.com/video/([A-Za-z0-9_-]{10}[AEIMQUYcgkosw048])(?:\?.*)?', re.IGNORECASE)
]

def coerce_to_id(vid):
    if not vid:
        return None
    if re.match(ID_PATTERN, vid):
        return vid

    for pattern in PATTERNS:
        newVid = re.sub(pattern, lambda match: match.group(1), vid)
        if re.match(ID_PATTERN, newVid):
            return newVid
    return None

def get_enabled_methods():
    titles = []
    for key in config_yml["methods"]:
        method = config_yml["methods"][key]
        if method["enabled"]:
            titles.append(method["title"])
    return titles

@app.route("/noscript_load.html")
async def noscript_load():
    if not request.args.get("d"):
        return "No d param provided - It should be the video id or url", 400
    id = coerce_to_id(request.args['d'])
    if not id:
        return render_template("templates/error.j2", inp=request.args['d']), 400
    headers = (("FinUrl", f"/noscript_load_thing.j2?id={id}"),)
    response = Response(render_template("noscript/loading.j2", id=id), headers=headers)
    return response, 302

@app.route("/api/coerce_to_id")
async def coerce_to_id_endpoint():
    if not request.args.get("d"):
        return '"No d param provided"', 400
    id = coerce_to_id(request.args['d'])
    if not id:
        return '"Could not parse the video ID out of that"', 400
    return {"data":id}

@app.route("/noscript_load_thing.html")
async def load_thing():
    if not request.args.get("id"):
        return "Missing id parameter", 400
    t = await youtube(3, request.args['id'], "youtube", json=False)
    return render_template("noscript/fid.j2", resp=t)

@app.after_request
async def apply_json_contenttype(response):
    if not request.path.startswith("/api"):
        return response
    try:
        json.loads(response.get_data(True))
    except json.JSONDecodeError:
        # Not JSON
        return response
    response.content_type = "application/json"
    return response

@app.route("/")
async def index():
    """
    Shows the landing page
    """
    default = request.args.get("q") or ""
    default_id = coerce_to_id(default) or ""
    return render_template("index.j2", default=default, default_id=default_id, methods=get_enabled_methods())

# The following code should be taken out and shot
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
    return render_template("api.j2", fields=responseDocstring, services=serviceDocstring, changelog=changelog)
