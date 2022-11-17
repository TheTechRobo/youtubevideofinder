from snscrape.base import _JSONDataclass as JSONDataclass

import config
import dataclasses
import time
import requests
import urllib.parse

from switch import Switch

from requests.auth import HTTPBasicAuth

from .types import *

class WaybackMachine(Service):
    name = "Wayback Machine"

    @classmethod
    def _run(cls, id) -> T:
        ismeta = False
        lien = f"https://web.archive.org/web/2oe_/http://wayback-fakeurl.archive.org/yt/{id}"
        response = requests.get(lien, allow_redirects=False, timeout=15)
        archived = True if response.headers.get("location") else False
        response2 = None
        if not archived:
            lien = None
            check = urllib.parse.quote(f"https://youtube.com/watch?v={id}", safe="") # not exhaustive but...
            response2 = requests.get(f"https://archive.org/wayback/available?url={check}", timeout=8).json()
            if response2["archived_snapshots"]:
                archived = True
                ismeta = True
                lien = response2["archived_snapshots"]["closest"]["url"]

        rawraw = (response.headers.get("location"), response2)
        return cls(
                archived=archived, capcount=int(archived), rawraw=rawraw,
                available=lien, lastupdated=time.time(), name=cls.getName(),
                note="", metaonly=ismeta, comments=False
        )

class InternetArchive(Service):
    name = "Internet Archive/archive.org"
    items_tried = [
        "youtube-%s",
        "youtube_%s",
        "%s"
    ]
    
    @classmethod
    def _run(cls, id) -> T:
        datas = []
        is_dark = False
        for template in cls.items_tried:
            ident = template % id
            data = requests.get(f"https://archive.org/metadata/{ident}", timeout=12).json()
            datas.append(data)
            if data.get("is_dark"):
                is_dark = True
            if data and (not data.get("is_dark")):
                is_dark = False
                break
        archived = bool(data)
        rawraw = datas
        lien = f"https://archive.org/details/{ident}" if archived else None
        note = ""
        if not archived:
            note = "Even if it isn't found here, it might still be in the Internet Archive. This site only checks for certain item identifiers."
            if is_dark:
                ianote = "This item is currently unavailable to the general public.<br>"  + IANOTE
        capcount = int(archived)
        return cls(
            archived=archived, capcount=capcount, available=lien, lastupdated=time.time(), name=cls.getName(), note=note,
            rawraw=rawraw, metaonly=False, comments=False
        )

class GhostArchive(Service):
    @classmethod
    def _run(cls, id) -> T:
        link = f"https://ghostarchive.org/varchive/{id}"
        code = requests.get(link).status_code
        archived: bool = False
        with Switch(code) as case:
            if case(200):
                archived = True
            if case(404):
                archived = False
            if case.default:
                raise AssertionError(f"bad status code (expected one of (200, 404), got {code})")
        capcount = int(archived)
        available = link if archived else None
        lastupdated = time.time()
        return cls(
            archived=archived, available=available, capcount=capcount, lastupdated=lastupdated, name=cls.getName(), note="", rawraw=code,
            metaonly=False, comments=False
        )

class Ya(Service):
    name = "#youtubearchive"
    note = ("To retrieve a video from #youtubearchive, join #youtubearchive on hackint IRC and ask for help. "
        "Remember <a href='https://wiki.archiveteam.org/index.php/Archiveteam:IRC#How_do_I_chat_on_IRC?'>IRC etiquette</a>!"
    )
    enabled = config.ya.enabled
    username = config.ya.username
    password = config.ya.password
    
    @classmethod
    def _run(cls, id):
        vid = id
        assert cls.enabled, "#youtubearchive API access is not enabled"
        auth = HTTPBasicAuth(cls.username, cls.password)
        comments = False
        data = requests.get("https://ya.borg.xyz/cgi-bin/capture-count?v=" + vid, auth=auth, timeout=5).text
        if not data:
            raise ValueError("Server returned empty response!")
        commentcount = requests.get("https://ya.borg.xyz/cgi-bin/capture-comment-counts?v="+vid, auth=auth).text
        count = int(data)
        archived = (count > 0)
        comments = [i for i in commentcount.split("\n") if i.strip("∅\n") and i.strip() != "0"]
        rawraw = (data, commentcount)
        return cls(
            archived=archived, capcount=count, comments=(len(comments) > 0), lastupdated=time.time(), name=cls.getName(),
            note=cls.note if archived else "", rawraw=rawraw, metaonly=False
        )

class Filmot(Service):
    key = config.filmot.key
    enabled = getattr(config.filmot, "enabled", False)

    lastretrieved: int = 0
    cooldown: int = 2

    @classmethod
    def _run(cls, id) -> T:
        while time.time() - cls.lastretrieved < cls.cooldown:
            time.sleep(0.1)
        cls.lastretrieved = time.time()
        lastupdated = time.time()
        assert cls.enabled, "Filmot API access is not enabled."
        data = requests.get(f"https://filmot.com/api/getvideos?key={cls.key}&id={id}&flags=1").json()
        archived = True
        if not data:
            archived = False
        capcount = int(archived)
        available = f"https://filmot.com/video/{id}" if archived else None
        return cls(
                archived=archived, capcount=capcount, error=False,
                lastupdated=lastupdated, name=cls.getName(), note="",
                rawraw=data, metaonly=True, comments=False,
                available=available
        )