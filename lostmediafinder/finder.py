"""
All the Service implementations live here.
"""

import time
import urllib.parse

import requests
from requests.auth import HTTPBasicAuth
from switch import Switch

import config
from .types import Service, T

class WaybackMachine(Service):
    """
    Queries the Wayback Machine for the video you requested.
    """
    name = "Wayback Machine"

    @classmethod
    def _run(cls, id, includeRaw=True) -> T:
        ismeta = False
        lien = f"https://web.archive.org/web/2oe_/http://wayback-fakeurl.archive.org/yt/{id}"
        response = requests.get(lien, allow_redirects=False, timeout=15)
        archived = bool(response.headers.get("location")) # if there's a redirect, it's archived
        response2 = None
        if not archived:
            lien = None
            check = urllib.parse.quote(f"https://youtube.com/watch?v={id}", safe="") # not exhaustive but...
            response2 = requests.get(f"https://archive.org/wayback/available?url={check}", timeout=8).json()
            if response2["archived_snapshots"]:
                archived = True
                ismeta = True
                lien = response2["archived_snapshots"]["closest"]["url"]

        rawraw = (response.headers.get("location"), response2) if includeRaw else None
        return cls(
                archived=archived, capcount=int(archived), rawraw=rawraw,
                available=lien, lastupdated=time.time(), name=cls.getName(),
                note="", metaonly=ismeta, comments=False
        )

class InternetArchive(Service):
    """
    Queries the Internet Archive for the video you requested.
    """
    name = "Internet Archive/archive.org"
    items_tried = [
        "youtube-%s",
        "youtube_%s",
        "%s"
    ]

    @classmethod
    def _run(cls, id, includeRaw=True) -> T:
        responses = []
        is_dark = False
        for template in cls.items_tried:
            ident = template % id
            metadata = requests.get(f"https://archive.org/metadata/{ident}", timeout=12).json()
            responses.append(metadata)
            if metadata.get("is_dark"):
                is_dark = True
            if metadata and (not metadata.get("is_dark")):
                is_dark = False
                break
        archived = bool(metadata)
        rawraw = responses if includeRaw else None
        lien = f"https://archive.org/details/{ident}" if archived else None
        note = ""
        if not archived:
            note = "Even if it isn't found here, it might still be in the Internet Archive. This site only checks for certain item identifiers."
            if is_dark:
                note = "An item was found, but it is currently unavailable to the general public.<br>" + note
        capcount = int(archived)
        return cls(
            archived=archived, capcount=capcount, available=lien, lastupdated=time.time(), name=cls.getName(), note=note,
            rawraw=rawraw, metaonly=False, comments=False
        )

class GhostArchive(Service):
    """
    Queries GhostArchive for the video you requested.
    """
    @classmethod
    def _run(cls, id, includeRaw=True) -> T:
        link = f"https://ghostarchive.org/varchive/{id}"
        code = requests.get(link).status_code
        rawraw = code if includeRaw else None
        archived = None
        with Switch(code) as case:
            if case(200):
                archived = True
            elif case(404):
                archived = False
            elif case.default:
                raise AssertionError(f"bad status code (expected one of (200, 404), got {code})")
            else:
                raise RuntimeError("We should never be here!")
        capcount = int(archived)
        available = link if archived else None
        lastupdated = time.time()
        return cls(
            archived=archived, available=available, capcount=capcount, lastupdated=lastupdated, name=cls.getName(), note="", rawraw=rawraw,
            metaonly=False, comments=False
        )

class Ya(Service):
    """
    Queries #youtubearchive for the video you requested.
    """
    name = "#youtubearchive"
    note = ("To retrieve a video from #youtubearchive, join #youtubearchive on hackint IRC and ask for help. "
        "Remember <a href='https://wiki.archiveteam.org/index.php/Archiveteam:IRC#How_do_I_chat_on_IRC?'>IRC etiquette</a>!"
    )
    enabled = config.ya.enabled
    username = config.ya.username
    password = config.ya.password

    @classmethod
    def _run(cls, id, includeRaw=True):
        vid = id
        assert cls.enabled, "#youtubearchive API access is not enabled"
        auth = HTTPBasicAuth(cls.username, cls.password)
        comments = False
        count = requests.get("https://ya.borg.xyz/cgi-bin/capture-count?v=" + vid, auth=auth, timeout=5).text
        if not count:
            raise ValueError("Server returned empty response!")
        commentcount = requests.get("https://ya.borg.xyz/cgi-bin/capture-comment-counts?v="+vid, auth=auth).text
        count = int(count)
        archived = (count > 0)
        comments = [i for i in commentcount.split("\n") if i.strip("∅\n") and i.strip() != "0"]
        rawraw = (count, commentcount) if includeRaw else None
        return cls(
            archived=archived, capcount=count, comments=(len(comments) > 0), lastupdated=time.time(), name=cls.getName(),
            note=cls.note if archived else "", rawraw=rawraw, metaonly=False
        )

class Filmot(Service):
    """
    Queries Filmot for the video you requested.
    """
    key = config.filmot.key
    enabled = getattr(config.filmot, "enabled", False)

    lastretrieved: int = 0
    cooldown: int = 2

    @classmethod
    def _run(cls, id, includeRaw=True) -> T:
        while time.time() - cls.lastretrieved < cls.cooldown:
            time.sleep(0.1)
        cls.lastretrieved = time.time()
        lastupdated = time.time()
        assert cls.enabled, "Filmot API access is not enabled."
        metadata = requests.get(f"https://filmot.com/api/getvideos?key={cls.key}&id={id}&flags=1").json()
        rawraw = metadata if includeRaw else None
        if len(metadata) > 0: # pylint: disable=simplifiable-if-statement
            archived = True
        else:
            archived = False
        capcount = int(archived)
        available = f"https://filmot.com/video/{id}" if archived else None
        return cls(
                archived=archived, capcount=capcount, error=False,
                lastupdated=lastupdated, name=cls.getName(), note="",
                rawraw=rawraw, metaonly=True, comments=False,
                available=available
        )
