import requests, config
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
    ret = {"capcount": 1 if archived else 0, "archived": archived, "rawraw": response.status_code, "suppl": None, "lastupdated": time.time(), "note": GNOTE, "name": GNAME, "available": lien if archived else None}
    GCACHE[vid] = ret
    return ret

FILNOTE = "Filmot only provides metadata, not the actual video."
FILNAME = "Filmot (metadata only)"
FILCACHE= {}
def filmot(vid):
    if FILCACHE.get(vid) and time.time() - FILCACHE[vid]["lastupdated"] < 10:
        return FILCACHE[vid]
    key = config.filmot.key
    res = requests.get(f"https://filmot.com/api/getvideos?key={key}&id={vid}")
    data = res.json()
    archived = bool(data)
    ret = {"archived": archived, "suppl": None, "rawraw": res.text, "lastupdated": time.time(), "note": FILNOTE, "name": FILNAME, "available": False}
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
    supplemental = None
    try:
        count = int(data)
    except ValueError:
        count = 0
    if not data:
        supplemental = "BAD_VID"
    archived = bool(count)
    NAHNOTE = YANOTE if archived else ""
    ret = {"capcount": count, "archived": archived, "rawraw": data, "suppl": supplemental, "lastupdated": time.time(), "name": YANAME, "note": NAHNOTE}
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
    ret = {"capcount": 1 if archived else 0, "archived": archived, "rawraw": response.headers.get("location"), "suppl": "NOIMPL", "available": response.headers.get("location"), "lastupdated": time.time(), "name": WBMNAME, "note": WBMNOTE}
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
    ret = {"capcount": capcount, "archived": True, "rawraw": data, "lastupdated": time.time(), "name": IANAME, "note": IANOT, "available": lien}
    IACACHE[vid] = ret
    return ret
