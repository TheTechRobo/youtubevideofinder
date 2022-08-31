import requests, config, urllib.parse
import time

from requests.auth import HTTPBasicAuth

GCACHE = {}
GNOTE  = ""
GNAME  = "GhostArchive"
def ghostget(vid):
    GNOT = GNOTE
    if GCACHE.get(vid) and time.time() - GCACHE[vid]["lastupdated"] < 10:
        return GCACHE[vid]
    lien = f"https://ghostarchive.org/varchive/{vid}"
    try:
        response = requests.get(lien, timeout=5)
    except Exception as ename:
        GNOT = f"An error occured retrieving data from GhostArchive. ({ename})"
        archived = False
        rawraw = {"exception": str(ename), "type": str(type(ename))}
    else:
        archived = response.status_code == 200
        rawraw = response.status_code
    ret = {"capcount": 1 if archived else 0, "archived": archived, "rawraw": response.status_code, "suppl": None, "lastupdated": time.time(), "note": GNOT, "name": GNAME, "available": lien if archived else None, "metaonly": False, "comments": False}
    GCACHE[vid] = ret
    return ret

FILNOTE = ""
FILNAME = "Filmot"
FILCACHE= {}
FILDEL  = 2
FILAST  = 0
def filmot(vid):
    global FILAST
    if FILCACHE.get(vid) and time.time() - FILCACHE[vid]["lastupdated"] < 20:
        return FILCACHE[vid]
    while time.time() - FILAST <= FILDEL:
        time.sleep(0.1)
    k = config.filmot.key
    try:
        res=requests.get(f"https://filmot.com/api/getvideos?key={k}&id={vid}",
            timeout=5)
    except Exception as ename:
        rawraw = {"exception": str(ename), "type": str(type(ename))}
        data = {}
        FILNOT = f"An error occured retreiving data from Filmot. ({ename})"
    else:
        FILNOT = FILNOTE
        rawraw = res.text
        data = res.json()
    FILAST = time.time()
    archived = bool(data)
    ret = {"capcount": 1 if archived else 0, "archived": archived, "suppl": None, "rawraw": rawraw, "lastupdated": time.time(), "note": FILNOT, "name": FILNAME, "available": False, "metaonly": True, "comments": False}
    FILCACHE[vid] = ret
    return ret

YACACHE = {}
YANOTE  = "To retrieve a video from #youtubearchive, join #youtubearchive on hackint IRC and ask for help. Remember <a href='https://wiki.archiveteam.org/index.php/Archiveteam:IRC#How_do_I_chat_on_IRC?'>IRC etiquette</a>!"
YANAME  = "#youtubearchive"
def yairc(vid):
    YANOT = YANOTE
    if not config.ya.enabled:
        return {}
    if YACACHE.get(vid) and time.time() - YACACHE[vid]["lastupdated"] < 10:
        return YACACHE[vid]
    auth = HTTPBasicAuth(config.ya.username, config.ya.password)
    comments = False
    try:
        data = requests.get("https://ya.borg.xyz/cgi-bin/capture-count?v=" + vid, auth=auth, timeout=5).text
        if not data:
            raise ValueError
        commentcount = requests.get("https://ya.borg.xyz/cgi-bin/capture-comment-counts?v="+vid, auth=auth).text
    except Exception as ename:
        counts = 0
        rawraw = {"exception": str(ename), "type": str(type(ename))}
        NAHNOTE = f"An error occured retreiving data from ya.borg.xyz ({ename})"
    else:
        try:
            count = int(data)
        except ValueError:
            count = 0
        archived = bool(count)
        NAHNOTE = YANOT if archived else ""
        counts = [i for i in commentcount.split("\n") if i.strip("∅\n") and i.strip() != "0"]
        rawraw = (data, commentcount)
    if counts:
        comments = True
    supplemental = None
    ret = {"capcount": count, "archived": archived, "rawraw": rawraw, "suppl": supplemental, "lastupdated": time.time(), "name": YANAME, "note": NAHNOTE, "metaonly": False, "comments": comments}
    YACACHE[vid] = ret
    return ret

WBMCACHE = {}
WBMNOTE  = ""
WBMNAME  = "Wayback Machine"
def wbm(vid):
    ismeta = False
    WBMNOT = ""
    if WBMCACHE.get(vid) and time.time() - WBMCACHE[vid]["lastupdated"] < 6000:
        return WBMCACHE[vid]
    lien = f"https://web.archive.org/web/2oe_/http://wayback-fakeurl.archive.org/yt/{vid}"
    try:
        response = requests.get(lien, allow_redirects=False, timeout=7)
        archived = True if response.headers.get("location") else False
        response2 = None
        if not archived:
            check = urllib.parse.quote(f"https://youtube.com/watch?v={vid}", safe="") # not exhaustive but...
            response2 = requests.get(f"https://archive.org/wayback/available?url={check}").json()
            if response2["archived_snapshots"]:
                archived = True
                ismeta = True
                lien = response2["archived_snapshots"]["closest"]["url"]

    except Exception as ename:
        rawraw = {"exception": str(ename), "type": str(type(ename))}
        WBMNOT = "An error occured retreiving data from the Wayback Machine."
        archived = False
        lien = None
    else:
        WBMNOT = WBMNOTE
        rawraw = (response.headers.get("location"), response2)
    if not archived:
        lien = None
    ret = {"capcount": 1 if archived else 0, "archived": archived, "rawraw": rawraw, "suppl": "NOIMPL", "available": lien, "lastupdated": time.time(), "name": WBMNAME, "note": WBMNOTE, "metaonly": ismeta, "comments": False}
    WBMCACHE[vid] = ret
    return ret

IACACHE = {}
IANOTE  = "Even if it isn't found here, it might still be in the Internet Archive. This site only checks for certain item identifiers."
IANAME  = "Internet Archive"
def iai(vid):
    if IACACHE.get(vid) and time.time() - IACACHE[vid]["lastupdated"] < 60:
        return IACACHE[vid]
    item_templates = [
            "youtube-%s",
            "youtube_%s",
            "%s"
    ]
    try:
        for template in item_templates:
            data= requests.get(f"https://archive.org/metadata/{template % vid}",
                timeout=7).json()
            if data and (not data.get("is_dark")):
                break
    except Exception as ename:
        rawraw = {"exception": str(ename), "type": str(type(ename))}
        capcount = 1
        IANOT = "An error occured retreiving data from IA (%s)" % str(ename)
        data = {}
        archived = False
    else:
        archived = bool(data)
        rawraw = data
        lien = f"https://archive.org/details/{template % vid}"
        archived = bool(data)
        IANOT = "" if archived else IANOTE
    if not data:
        ret = {"capcount": 0, "archived": False, "rawraw": data, "lastupdated": time.time(), "name": IANAME, "note": IANOT}
        IACACHE[vid] = ret
        return ret
    capcount = 1
    if data.get("is_dark"):
        capcount = 0
        IANOT = "This item is currently unavailable to the general public.<br>"  + IANOTE
    ret = {"capcount": capcount, "archived": True, "rawraw": rawraw, "lastupdated": time.time(), "name": IANAME, "note": IANOT, "available": lien, "metaonly": False, "comments": False}
    IACACHE[vid] = ret
    return ret
