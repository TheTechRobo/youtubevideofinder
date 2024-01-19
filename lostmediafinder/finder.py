"""
All the Service implementations live here.
"""

import random, time, urllib.parse, aiohttp, asyncio
from switch import Switch
from .types import YouTubeService, T, methods

class YouTube(YouTubeService):
    """
    Checks if the video is still available on YouTube.
    Thumbnail method has a few edge cases but seems the most reliable for all tested cases.
    """
    name = methods["youtube"]["title"]
    configId = "youtube"

    @classmethod
    async def _run(cls, id, session: aiohttp.ClientSession) -> T:
        lien = f"https://i.ytimg.com/vi/{id}/hqdefault.jpg"
        async with session.head(lien, allow_redirects=False, timeout=15) as response:
            code = response.status

        rawraw = code
        archived = None
        link = f"https://youtu.be/{id}"

        if code == 200:
            archived = True
        else:
            archived = False

        capcount = int(archived)
        available = link if archived else None
        lastupdated = time.time()
        return cls(
            archived=archived, available=available, capcount=capcount, lastupdated=lastupdated, name=cls.getName(), note="", rawraw=rawraw,
            metaonly=False, comments=False
        )

class WaybackMachine(YouTubeService):
    """
    Queries the Wayback Machine for the video you requested.
    """
    name = methods["ia_wayback"]["title"]
    configId = "ia_wayback"

    @classmethod
    async def _run(cls, id, session: aiohttp.ClientSession) -> T:
        ismeta = False
        lien = f"https://web.archive.org/web/2oe_/http://wayback-fakeurl.archive.org/yt/{id}"
        async with session.head(lien, allow_redirects=False, timeout=15) as response:
            redirect = response.headers.get("location")
            archived = bool(redirect) # if there's a redirect, it's archived
        response2 = None
        if not archived:
            lien = None
            check = f"https://youtube.com/watch?v={id}" # not exhaustive but...
            params = {
                "url": check,
                "timestamp": 0
            }
            async with session.get(f"https://archive.org/wayback/available", params=params, timeout=8) as resp:
                response2 = await resp.json()
                if response2["archived_snapshots"]:
                    archived = True
                    ismeta = True
                    lien = response2["archived_snapshots"]["closest"]["url"]

        rawraw = (redirect, response2)
        return cls(
                archived=archived, capcount=int(archived), rawraw=rawraw,
                available=lien, lastupdated=time.time(), name=cls.getName(),
                note="", metaonly=ismeta, comments=False
        )

class ArchiveOrgDetails(YouTubeService):
    """
    Queries the Internet Archive for the video you requested.
    """
    name = methods["ia_details"]["title"]
    configId = "ia_details"
    items_tried = [
        "youtube-%s",
        "youtube_%s",
        "%s"
    ]

    @classmethod
    async def _run(cls, id, session: aiohttp.ClientSession) -> T:
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
        rawraw = responses
        lien = f"https://archive.org/details/{ident}" if archived else None
        note = ""
        if not archived:
            note = "Even if it isn't found here, it might still be in the Internet Archive. This site only checks for certain item identifiers."
            if is_dark:
                note = "An item was found, but it is currently unavailable to the general public.<br>" + note
            # Helper source code is at endpoint /source_code
            # This is the stash of IDs to idents #youtubearchive gave me
            # TODO: Should this be moved to the #youtubearchive scraper?
            helper_url = f"https://fyt-helper.thetechrobo.ca/ia_extra/{ident}"
            async with session.get(helper_url) as resp:
                if resp.status == 200:
                    archived = True
                    j = await resp.json()
                    lien = f"https://archive.org/details/{j['item']}"
                    note = "The item found was a generic channel item. It may contain multiple videos."
        capcount = int(archived)
        return cls(
            archived=archived, capcount=capcount, available=lien, lastupdated=time.time(), name=cls.getName(), note=note,
            rawraw=rawraw, metaonly=False, comments=False
        )


class ArchiveOrgCDX(YouTubeService):
    """
    Queries the Archive.org CDX for an archived video thumb
    """
    name = methods["ia_cdx"]["title"]
    configId = "ia_cdx"

    @classmethod
    async def _run(cls, id, session: aiohttp.ClientSession) -> T:
        cdx_urls = [
            f"https://web.archive.org/cdx/search/cdx?url=i.ytimg.com/vi/{id}*&collapse=digest&filter=statuscode:200&mimetype:image/jpeg&output=json",
            f"https://web.archive.org/cdx/search/cdx?url=i1.ytimg.com/vi/{id}*&collapse=digest&filter=statuscode:200&mimetype:image/jpeg&output=json",
            f"https://web.archive.org/cdx/search/cdx?url=i2.ytimg.com/vi/{id}*&collapse=digest&filter=statuscode:200&mimetype:image/jpeg&output=json",
            f"https://web.archive.org/cdx/search/cdx?url=i3.ytimg.com/vi/{id}*&collapse=digest&filter=statuscode:200&mimetype:image/jpeg&output=json",
            f"https://web.archive.org/cdx/search/cdx?url=i4.ytimg.com/vi/{id}*&collapse=digest&filter=statuscode:200&mimetype:image/jpeg&output=json",
            f"https://web.archive.org/cdx/search/cdx?url=i.ytimg.com/vi_webp/{id}*&collapse=digest&filter=statuscode:200&mimetype:image/webp&output=json",
            f"https://web.archive.org/cdx/search/cdx?url=s.ytimg.com/vi/{id}*&collapse=digest&filter=statuscode:200&mimetype:image/jpeg&output=json",
            f"https://web.archive.org/cdx/search/cdx?url=ytimg.googleusercontent.com/vi/{id}*&collapse=digest&filter=statuscode:200&mimetype:image/webp&output=json",
            f"https://web.archive.org/cdx/search/cdx?url=img.youtube.com/vi/{id}*&collapse=digest&filter=statuscode:200&mimetype:image/jpeg&output=json",
        ]

        results = []
        for cdx in cdx_urls:
            async with session.get(cdx, timeout=12) as resp:
                metadata = await resp.json()
            for result in metadata:
                if result[0] != 'urlkey':
                    results.append(result)

        # sort and select the most recent of highest quality version available
        results.sort(key=lambda x: x[1], reverse=True)
        quality_order = [
            'maxresdefault.jpg',
            'sddefault.jpg',
            'hqdefault.jpg',
            '0.jpg',
            'high.jpg',
            'mqdefault.jpg',
            'medium.jpg',
            'default.jpg',
            '1.jpg',
            '2.jpg',
            '3.jpg',
        ]
        def get_int(url):
            for i in range(len(quality_order)):
                if quality_order[i] in url:
                    return i

            return len(quality_order) + 1
        results.sort(key=lambda x: get_int(x[2]))

        if len(results) > 0:
            lien = f"https://web.archive.org/web/{results[0][1]}/{results[0][2]}"
            ismeta = True
            archived = True
        else:
            lien = None
            ismeta = False
            archived = False

        return cls(
                archived=archived, capcount=int(archived), rawraw=None,
                available=lien, lastupdated=time.time(), name=cls.getName(),
                note="", metaonly=ismeta, comments=False
        )


class GhostArchive(YouTubeService):
    """
    Queries GhostArchive for the video you requested.
    """
    name = methods["ghostarchive"]["title"]
    configId = "ghostarchive"

    @classmethod
    async def _run(cls, id, session: aiohttp.ClientSession) -> T:
        link = f"https://ghostarchive.org/varchive/{id}"
        async with session.get(link) as resp:
            code = resp.status
        rawraw = code
        archived = None
        with Switch(code) as case:
            if case(200):
                archived = True
            elif case(404):
                archived = False
            elif case(500):
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

class HackintYa(YouTubeService):
    """
    Queries #youtubearchive for the video you requested.
    """
    name = methods["hackint_ya"]["title"]
    note = ("At the request of #youtubearchive's maintainer, instructions to request videos have been removed. If you are significantly involved in archiving or open source, you have a legitimate research or humanitarian purpose, or are able to contribute materially, contact me at thetechrobo@proton.me.")
    configId = "hackint_ya"

    @classmethod
    async def _run(cls, id, session: aiohttp.ClientSession):
        username = methods[cls.configId]["username"]
        password = methods[cls.configId]["password"]

        vid = id
        auth = aiohttp.BasicAuth(username, password)
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
        rawraw = (count, commentcount)
        return cls(
            archived=archived, capcount=count, comments=(len(comments) > 0), lastupdated=time.time(), name=cls.getName(),
            note=cls.note if archived else "", rawraw=rawraw, metaonly=False
        )

FYT_UA = "FindYoutubeVideo/1.0 operated by TheTechRobo"

class DistributedYoutubeArchive(YouTubeService):
    """
    Queries DYA for the video in question.
    """
    name = methods['distributed_youtube_archive']['title']
    configId = "distributed_youtube_archive"

    @classmethod
    async def _run(cls, id, session: aiohttp.ClientSession):
        user_agent = FYT_UA
        lastupdated = time.time()
        async with session.get(f"https://dya-t-api.strangled.net/api/video/{id}") as resp:
            status = resp.status
            if status not in (200, 404):
                raise RuntimeError(f"DYA returned bad status code {status}")
            j = await resp.json()
            if "contributions" not in j:
                j['contributions_length'] = None
                assert "error" in j, "No error or contributions field returned"
                archived = False
            elif not j['contributions']:
                j['contributions_length'] = len(j['contributions'])
                del j['contributions']
                archived = False
            else:
                j['contributions_length'] = len(j['contributions'])
                del j['contributions']
                archived = True
        capcount = j['contributions_length']
        note = "One or more contributors to the Distributed YouTube Archive have the video. Join their Discord server and ask for help." if archived else ""
        metaonly = False
        comments = None # we can't tell whether there are comments or not
        available = "https://discord.gg/YNeVJ72NS4" if archived else None
        return cls(
            archived=archived, capcount=capcount, lastupdated=lastupdated,
            name=cls.getName(), note=note, rawraw=j, metaonly=metaonly,
            comments=comments, available=available
        )

class Hobune(YouTubeService):
    """
    Queries Hobune.stream for the video in question.
    """
    name = methods["hobune_stream"]["title"]
    configId = "hobune_stream"
    lastretrieved = 0
    cooldown = 0.5

    @classmethod
    async def _run(cls, id, session: aiohttp.ClientSession):
        while time.time() - cls.lastretrieved < cls.cooldown:
            await asyncio.sleep(0.1)
        user_agent = "FindYoutubeVideo/1.0 operated by thetechrobo@proton.me"
        urls_to_try = ("https://hobune.stream/videos/{}", "https://hobune.stream/tpa-h/videos/{}")
        raw = []
        archived = False
        available = None
        lastupdated = time.time()
        cls.lastretrieved = lastupdated
        for url in urls_to_try:
            url = url.format(id)
            async with session.head(url, headers={"User-Agent": user_agent}, timeout=5) as resp:
                code = resp.status
                raw.append(code)
            if code == 200:
                archived = True
                available = url
                break
            elif code == 404:
                archived = False
                available = None
            else:
                raise RuntimeError("Hobune.stream returned invalid status code %s" % code)
        return cls(
            archived=archived, capcount=1 if archived else 0,
            lastupdated=lastupdated, name=cls.getName(), note="",
            rawraw=raw, metaonly=False, comments=False, available=available
        )

# TODO: Make a YouTubeServiceWithCooldown or something

class Filmot(YouTubeService):
    """
    Queries Filmot for the video you requested.
    """
    name = methods["filmot"]["title"]
    lastretrieved: int = 0
    cooldown: int = 2
    configId = "filmot"

    @classmethod
    async def _run(cls, id, session: aiohttp.ClientSession) -> T:
        key = methods[cls.configId]["api_key"]

        while time.time() - cls.lastretrieved < cls.cooldown:
            await asyncio.sleep(0.1)
        lastupdated = time.time()
        cls.lastretrieved = time.time()
        async with session.get(f"https://filmot.com/api/getvideos?key={key}&id={id}&flags=1") as resp:
            metadata = await resp.json(content_type=None)
        rawraw = metadata
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
    name = methods["playboard_co"]["title"]
    note = "The Playboard scraper is unreliable; please verify values yourself."
    configId = "playboard_co"

    @classmethod
    async def _run(cls, id, session: aiohttp.ClientSession):
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
