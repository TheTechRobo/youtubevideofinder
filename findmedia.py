import requests, config, urllib.parse
import time

from requests.auth import HTTPBasicAuth

GCACHE = {}
GNOTE  = ""
GNAME  = "GhostArchive"
def ghostget(vid):
    if GCACHE.get(vid) and time.time() - GCACHE[vid]["lastupdated"] < 10:
        return GCACHE[vid]
    lien = f"https://ghostarchive.org/varchive/{vid}"
    response = requests.get(lien)
    archived = response.status_code == 200
    ret = {"capcount": 1 if archived else 0, "archived": archived, "rawraw": response.status_code, "suppl": None, "lastupdated": time.time(), "note": GNOTE, "name": GNAME, "available": lien if archived else None, "metaonly": False}
    GCACHE[vid] = ret
    return ret

FILNOTE = "Filmot only provides metadata, not the actual video."
FILNAME = "Filmot (metadata only)"
FILCACHE= {}
FILDEL  = 2
FILAST  = 0
def filmot(vid):
    global FILAST
    if FILCACHE.get(vid) and time.time() - FILCACHE[vid]["lastupdated"] < 20:
        return FILCACHE[vid]
    while time.time() - FILAST <= FILDEL:
        time.sleep(0.1)
    key = config.filmot.key
    res = requests.get(f"https://filmot.com/api/getvideos?key={key}&id={vid}")
    FILAST = time.time()
    data = res.json()
    archived = bool(data)
    ret = {"capcount": 1 if archived else 0, "archived": archived, "suppl": None, "rawraw": res.text, "lastupdated": time.time(), "note": FILNOTE, "name": FILNAME, "available": False, "metaonly": False}
    FILCACHE[vid] = ret
    return ret

YACACHE = {}
YANOTE  = "To retrieve a video from #youtubearchive, join #youtubearchive on hackint IRC and ask for help. Remember <a href='https://wiki.archiveteam.org/index.php/Archiveteam:IRC#How_do_I_chat_on_IRC?'>IRC etiquette</a>!"
YANAME  = "#youtubearchive"
def yairc(vid):
    if not config.ya.enabled:
        return {}
    if YACACHE.get(vid) and time.time() - YACACHE[vid]["lastupdated"] < 10:
        return YACACHE[vid]
    auth = HTTPBasicAuth(config.ya.username, config.ya.password)
    data = requests.get("https://ya.borg.xyz/cgi-bin/capture-count?v=" + vid, auth=auth).text
    comments = False
    commentcount = requests.get("https://ya.borg.xyz/cgi-bin/capture-comment-counts?v="+vid, auth=auth).text
    counts = [i for i in commentcount.split("\n") if i.strip("∅\n") and i.strip() != "0"]
    if counts:
        comments = True
    supplemental = None
    try:
        count = int(data)
    except ValueError:
        count = 0
    if not data:
        supplemental = "BAD_VID"
    archived = bool(count)
    NAHNOTE = YANOTE if archived else ""
    ret = {"capcount": count, "archived": archived, "rawraw": (data, commentcount), "suppl": supplemental, "lastupdated": time.time(), "name": YANAME, "note": NAHNOTE, "metaonly": False, "comments": comments}
    YACACHE[vid] = ret
    return ret

WBMCACHE = {}
WBMNOTE  = ""
WBMNAME  = "Wayback Machine"
def wbm(vid):
    if WBMCACHE.get(vid) and time.time() - WBMCACHE[vid]["lastupdated"] < 6000:
        return WBMCACHE[vid]
    response = requests.get(f"https://web.archive.org/web/2oe_/http://wayback-fakeurl.archive.org/yt/{vid}", allow_redirects=False)
    archived = True if response.headers.get("location") else False
    lien = response.headers.get("location")
    ismeta = False
    response2 = None
    if not archived:
        check = urllib.parse.quote(f"https://youtube.com/watch?v={vid}", safe="") # not exhaustive but...
        response2 = requests.get(f"https://archive.org/wayback/available?url={check}").json()
        if response2["archived_snapshots"]:
            archived = True
            ismeta = True
            lien = response2["archived_snapshots"]["closest"]["url"]
    ret = {"capcount": 1 if archived else 0, "archived": archived, "rawraw": (response.headers.get("location"), response2), "suppl": "NOIMPL", "available": lien, "lastupdated": time.time(), "name": WBMNAME, "note": WBMNOTE, "metaonly": ismeta}
    WBMCACHE[vid] = ret
    return ret

IACACHE = {}
IANOTE  = "Even if it isn't found here, it might still be in the Internet Archive. This site only checks for 'youtube-VIDEOID items."
IANAME  = "Internet Archive"
def iai(vid):
    if IACACHE.get(vid) and time.time() - IACACHE[vid]["lastupdated"] < 60:
        return IACACHE[vid]
    data = requests.get("https://archive.org/metadata/youtube-" + vid).json()
    if not data:
        ret = {"capcount": 0, "archived": False, "rawraw": data, "lastupdated": time.time(), "name": IANAME, "note": IANOTE}
        IACACHE[vid] = ret
        return ret
    capcount = 1
    IANOT = ""
    lien = f"https://archive.org/details/youtube-{vid}"
    if data.get("is_dark"):
        capcount = 0
        IANOT = "This item is currently unavailable to the general public.<br>"  + IANOTE
    ret = {"capcount": capcount, "archived": True, "rawraw": data, "lastupdated": time.time(), "name": IANAME, "note": IANOT, "available": lien, "metaonly": False}
    IACACHE[vid] = ret
    return ret
