import dataclasses, itertools
from quart import Quart, render_template, request, Response, redirect, send_from_directory, url_for
import re, yaml, json
import lostmediafinder

class EscapingQuart(Quart):
    def select_jinja_autoescape(self, filename: str) -> bool:
        return filename.endswith(".j2") or super().select_jinja_autoescape(filename)

app = EscapingQuart(__name__)

with open('config.yml', 'r') as file:
    config_yml = yaml.safe_load(file)

@app.route("/robots.txt")
async def robots():
    return await send_from_directory("static", "robots.txt")

@app.route("/find/<id>")
async def youtubev2(id):
    """
    Provides backwards compatibility for the old endpoint.
    """
    return (await lostmediafinder.YouTubeResponse.generate(id)).coerce_to_api_version(2).json(), {"Content-Type": "application/json"}

async def wrapperYT(id, includeRaw):
    """
    Wrapper for generate
    """
    try:
        return await lostmediafinder.YouTubeResponse.generate(id, includeRaw)
    except lostmediafinder.types.InvalidVideoIdError:
        return {"status": "bad.id", "id": None}

async def wrapperYTS(id, includeRaw):
    """
    Wrapper for generateStream
    """
    return await lostmediafinder.YouTubeResponse.generateStream(id, includeRaw)

@app.route("/api/v<int:v>/<site>/<id>")
@app.route("/api/v<int:v>/<id>")
async def youtube(v, id, site="youtube", jsn=True):
    includeRaw = True
    if v == 1:
        return "This API version is no longer supported.", 410
    if v not in (2, 3, 4, 5):
        return "Unrecognised API version", 404
    if site == "youtube":
        includeRaw = True
        stream = False
        if v >= 4:
            stream = "stream" in request.args
            # Versions 4 and higher only provide `rawraw` if you ask for it
            includeRaw = "includeRaw" in request.args
        if stream:
            async def run():
                r = (await wrapperYTS(id, includeRaw=includeRaw)).coerce_to_api_version(v)
                async for item in r:
                    if type(item) == dict or item is None:
                        yield json.dumps(item) + "\n"
                    else:
                        yield item.json() + "\n"
            return run(), {"Content-Type": "application/json"}
        else:
            r = (await wrapperYT(id, includeRaw=includeRaw)).coerce_to_api_version(v)
            if jsn:
                return r.json(), {"Content-Type": "application/json"}
            return r
    return "Unrecognised site", 404

@app.route("/noscript_init.html")
async def noscript_init():
    if id := request.args.get("d"):
        return redirect("/noscript_load.html?d=" + id)
    return await render_template("noscript/init.j2")

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
        return await render_template("noscript/error.j2", inp=request.args['d']), 400
    headers = (("FinUrl", f"/noscript_load_thing.j2?id={id}"),)
    response = Response(await render_template("noscript/loading.j2", id=id), headers=headers)
    return response, 302

@app.route("/api/coerce_to_id")
async def coerce_to_id_endpoint():
    if not request.args.get("d"):
        return '"No d param provided"', 400
    id = coerce_to_id(request.args['d'])
    if not id:
        return '"Unable to find a video ID"', 400
    return {"data":id}

@app.route("/noscript_load_thing.html")
async def load_thing():
    if not request.args.get("id"):
        return "Missing id parameter", 400
    t = await youtube(5, request.args['id'], "youtube", jsn=False)
    assert isinstance(t, lostmediafinder.YouTubeResponse)
    t.keys = list(itertools.chain(
        (k for k in t.keys if k.archived and not k.error),
        (k for k in t.keys if k.error),
        (k for k in t.keys if not k.error and not k.archived)
    ))
    return await render_template("noscript/fid.j2", resp=t, list=list, asd=dataclasses.asdict)

@app.route("/")
async def index():
    """
    Shows the landing page
    """
    default = request.args.get("q") or ""
    default_id = coerce_to_id(default) or ""
    if default and default_id and default != default_id:
        return redirect(url_for("index", q=default_id))
    absolute_url = url_for(
        "index",
        _external=True
    ) + "?q=https://youtube.com/watch?v=dQw4w9WgXcQ"
    return await render_template(
        "index.j2",
        default=default,
        default_id=default_id,
        methods=get_enabled_methods(),
        absolute_url=absolute_url
    )

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
    linkDocstring = lostmediafinder.Link.__doc__
    # Parse the attributes list
    responseDocstring = await parse_lines(responseDocstring.split("Attributes:\n")[1].strip().split("\n"))
    serviceDocstring  = await parse_lines(serviceDocstring.split("Attributes:\n")[1].strip().split("\n"))
    linkDocstring = await parse_lines(linkDocstring.split("Attributes:\n")[1].strip().split("\n"))
    return await render_template("api.j2", fields=responseDocstring, services=serviceDocstring, links=linkDocstring)
