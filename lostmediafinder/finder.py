"""
All the Service implementations live here.
"""

import random
import time
import urllib.parse

import aiohttp
from switch import Switch

from .types import YouTubeService, T

class WaybackMachine(YouTubeService):
    """
    Queries the Wayback Machine for the video you requested.
    """
    name = "Wayback Machine"

    @classmethod
    async def _run(cls, id, session: aiohttp.ClientSession, includeRaw=True) -> T:
        ismeta = False
        lien = f"https://web.archive.org/web/2oe_/http://wayback-fakeurl.archive.org/yt/{id}"
        async with session.head(lien, allow_redirects=False, timeout=15) as response:
            redirect = response.headers.get("location")
            archived = bool(redirect) # if there's a redirect, it's archived
        response2 = None
        if not archived:
            lien = None
            check = urllib.parse.quote(f"https://youtube.com/watch?v={id}", safe="") # not exhaustive but...
            async with session.get(f"https://archive.org/wayback/available?url={check}", timeout=8) as resp:
                response2 = await resp.json()
                if response2["archived_snapshots"]:
                    archived = True
                    ismeta = True
                    lien = response2["archived_snapshots"]["closest"]["url"]

        rawraw = (redirect, response2) if includeRaw else None
        return cls(
                archived=archived, capcount=int(archived), rawraw=rawraw,
                available=lien, lastupdated=time.time(), name=cls.getName(),
                note="", metaonly=ismeta, comments=False
        )

class InternetArchive(YouTubeService):
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
    async def _run(cls, id, session: aiohttp.ClientSession, includeRaw=True) -> T:
        responses = []
        is_dark = False
        for template in cls.items_tried:
            ident = template % id
            async with session.get(f"https://archive.org/metadata/{ident}", timeout=12) as resp:
                metadata = await resp.json()
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

class GhostArchive(YouTubeService):
    """
    Queries GhostArchive for the video you requested.
    """
    @classmethod
    async def _run(cls, id, session: aiohttp.ClientSession, includeRaw=True) -> T:
        link = f"https://ghostarchive.org/varchive/{id}"
        async with session.get(link) as resp:
            code = resp.status
        rawraw = code if includeRaw else None
        archived = None
        with Switch(code) as case:
            if case(200):
                archived = True
            elif case(404):
                archived = False
            elif case.default:
                raise AssertionError(f"bad status code (expected one of (200, 404, 500), got {code})")
            else:
                raise RuntimeError("We should never be here!")
        capcount = int(archived)
        available = link if archived else None
        lastupdated = time.time()
        return cls(
            archived=archived, available=available, capcount=capcount, lastupdated=lastupdated, name=cls.getName(), note="", rawraw=rawraw,
            metaonly=False, comments=False
        )

class Ya(YouTubeService):
    """
    Queries #youtubearchive for the video you requested.
    """
    name = "#youtubearchive"
    note = ("To retrieve a video from #youtubearchive, join #youtubearchive on hackint IRC and ask for help. "
        "Remember <a href='https://wiki.archiveteam.org/index.php/Archiveteam:IRC#How_do_I_chat_on_IRC?'>IRC etiquette</a>!"
    )

    @classmethod
    async def _run(cls, id, session: aiohttp.ClientSession, includeRaw=True):
        vid = id
        assert cls._getFromConfig("ya", "enabled"), "#youtubearchive API access is not enabled"
        auth = aiohttp.BasicAuth(cls._getFromConfig("ya", "username"), cls._getFromConfig("ya", "password"))
        comments = False
        async with session.get("https://ya.borg.xyz/cgi-bin/capture-count?v=" + vid, auth=auth, timeout=5) as resp:
            count = await resp.text()
        if not count:
            raise ValueError("Server returned empty response!")
        count = int(count)
        async with session.get("https://ya.borg.xyz/cgi-bin/capture-comment-counts?v=" + vid, auth=auth) as resp:
            commentcount = await resp.text()
        archived = (count > 0)
        comments = [i for i in commentcount.split("\n") if i.strip("∅\n") and i.strip() != "0"]
        rawraw = (count, commentcount) if includeRaw else None
        return cls(
            archived=archived, capcount=count, comments=(len(comments) > 0), lastupdated=time.time(), name=cls.getName(),
            note=cls.note if archived else "", rawraw=rawraw, metaonly=False
        )

# TODO: Make a YouTubeServiceWithCooldown or something

class Filmot(YouTubeService):
    """
    Queries Filmot for the video you requested.
    """
    lastretrieved: int = 0
    cooldown: int = 2

    @classmethod
    async def _run(cls, id, session: aiohttp.ClientSession, includeRaw=True) -> T:
        enabled = cls._getFromConfig("filmot", "enabled")
        assert enabled, "Filmot API access is not enabled."
        key = cls._getFromConfig("filmot", "key")
        while time.time() - cls.lastretrieved < cls.cooldown:
            time.sleep(0.1)
        lastupdated = time.time()
        cls.lastretrieved = time.time()
        lastupdated = time.time()
        async with session.get(f"https://filmot.com/api/getvideos?key={key}&id={id}&flags=1") as resp:
            metadata = await resp.json(content_type=None)
        rawraw = metadata if includeRaw else None
        if len(metadata) > 0: # pylint: disable=simplifiable-if-statement
            archived = True
        else:
            archived = False
        capcount = int(archived)
        available = f"https://filmot.com/video/{id}" if archived else None
        return cls(
                archived=archived, capcount=capcount,
                lastupdated=lastupdated, name=cls.getName(), note="",
                rawraw=rawraw, metaonly=True, comments=False,
                available=available
        )

class Playboard(YouTubeService):
    """
    Queries Playboard.co for whether it's archived or not.
    Playboard is metadata-only as far as I know.
    """
    name = "Playboard.co"
    note = "The Playboard scraper is unreliable; please verify values yourself."

    @classmethod
    async def _run(cls, id, session: aiohttp.ClientSession, includeRaw=True):
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.%s.0.0 Safari/537.36"
        user_agent = user_agent % random.randint(0, 100)
        url = f"https://playboard.co/en/video/{id}"
        async with session.get(url, headers={"User-Agent": user_agent}) as resp:
            code = resp.status
        rawraw = {"status_code": code, "ua_used": user_agent}
        lastupdated = time.time()
        available = None
        if code in {200, 429}:
            archived = True
            available = url
        elif code == 404:
            archived = False
        else:
            raise AssertionError(f"bad status code {code}")
        return cls(
                archived=archived, capcount=1 if archived else 0,
                lastupdated=lastupdated, name=cls.getName(), note=cls.note,
                rawraw=rawraw, metaonly=True, comments=False,
                available=available
        )

