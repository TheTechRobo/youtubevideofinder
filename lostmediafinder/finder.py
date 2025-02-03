"""
All the Service implementations live here.
"""

import random, time, urllib.parse, aiohttp, asyncio
import typing_extensions as typing
from switch import Switch
from .types import YouTubeService, methods, experiment_base_url
from yarl import URL

async def submit_experiment(session: aiohttp.ClientSession, experiment_name: str, video_id: str):
    if experiment_base_url:
        report = {
            "experiment": experiment_name,
            "id": video_id,
        }
        try:
            await session.post(experiment_base_url, json=report)
        except Exception:
            pass

class YouTube(YouTubeService):
    """
    Checks if the video is still available on YouTube.
    Thumbnail method has a few edge cases but seems the most reliable for all tested cases.
    """
    name = methods["youtube"]["title"]
    configId = "youtube"

    @classmethod
    async def _run(cls, id, session: aiohttp.ClientSession) -> typing.Self:
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
            metaonly=False, comments=False, classname=cls.__name__
        )


class WaybackMachine(YouTubeService):
    """
    Queries the Wayback Machine for the video you requested.
    """
    name = methods["ia_wayback"]["title"]
    configId = "ia_wayback"

    @classmethod
    async def _run(cls, id: str, session: aiohttp.ClientSession) -> typing.Self:
        ismeta = False
        lien = f"https://web.archive.org/web/0id_/http://wayback-fakeurl.archive.org/yt/{id}"

        async with session.head(lien, allow_redirects=False, timeout=15) as response:
            redirect = response.headers.get("location")
            archived = bool(redirect)  # Archived if there is a redirect
            if redirect:
                u = URL(redirect)
                assert u.path != "/sry", "Redirected to sorry page. Is IA down?"
            fakeurl_archived = archived

        params = {"vtype": "youtube", "vid": id}
        async with session.get("https://web.archive.org/__wb/videoinfo", params=params, timeout=5) as response:
            viresp = await response.json()
            videoinfo_archived = bool(viresp.get("formats"))
            if videoinfo_archived:
                archived = True
        if fakeurl_archived != videoinfo_archived:
            await submit_experiment(session, "wb-index-weirdness", id)
            if videoinfo_archived:
                # TODO: better sorting system; right now while this is
                # an edge case I'm not going to bother, but if it ever is the default
                # this should be improved
                format = viresp['formats'][0]
                url, ts = format['url'], format['timestamp']
                lien = f"https://web.archive.org/web/{ts}/{url}"

        response2 = None
        url_formats = [
            f"youtube.com/watch?v={id}",
            f"youtube.com/embed/{id}",
            f"youtube.com/shorts/{id}",
            f"youtu.be/{id}"
        ]

        # CDX above Availability because currently, latter will return text/html MIME type,
        # which causes the script to unalive itself, prematurely
        if not archived:
            for check in url_formats:
                params = {
                    "url": check,
                    "collapse": "urlkey",
                    "filter": "statuscode:200",
                    "output": "json"
                }
                try:
                    async with session.get("https://web.archive.org/cdx/search/cdx", params=params, timeout=15) as cdx_resp:
                        cdx_results = await cdx_resp.json()
                        if cdx_results:
                            lien = f"https://web.archive.org/web/{cdx_results[1][1]}/{cdx_results[1][2]}"
                            archived = True
                            ismeta = True
                            break
                except (aiohttp.ClientError, asyncio.TimeoutError):
                    continue

        if not archived:
            lien = None
            for check in url_formats:
                params = {
                    "url": check,
                    "timestamp": 0
                }
                async with session.get("https://archive.org/wayback/available", params=params, timeout=15) as resp:
                    response2 = await resp.json()
                    if response2.get("archived_snapshots"):
                        archived = True
                        ismeta = True
                        lien = response2["archived_snapshots"]["closest"]["url"]
                        break

        rawraw = (redirect, viresp, response2)
        return cls(
            archived=archived, capcount=int(archived), rawraw=rawraw, available=lien,
            lastupdated=time.time(), name=cls.getName(), note="", metaonly=ismeta,
            comments=False, classname=cls.__name__
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
    async def _run(cls, id, session: aiohttp.ClientSession) -> typing.Self:
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
            rawraw=rawraw, metaonly=False, comments=False, classname=cls.__name__
        )


class ArchiveOrgCDX(YouTubeService):
    """
    Queries the Archive.org CDX for an archived video thumb
    """
    name = methods["ia_cdx"]["title"]
    configId = "ia_cdx"

    @classmethod
    async def _run(cls, id, session: aiohttp.ClientSession) -> typing.Self:
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
                note="", metaonly=ismeta, comments=False, classname=cls.__name__
        )


class GhostArchive(YouTubeService):
    """
    Queries GhostArchive for the video you requested.
    """
    name = methods["ghostarchive"]["title"]
    configId = "ghostarchive"

    @classmethod
    async def _run(cls, id, session: aiohttp.ClientSession) -> typing.Self:
        link = f"https://ghostarchive.org/varchive/{id}"
        async with session.get(link, timeout=5) as resp:
            code = resp.status
            ct = await resp.text()
        rawraw = code
        archived = None
        with Switch(code) as case:
            if case(200):
                archived = True
                assert "Visit the main page" in ct
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
            metaonly=False, comments=False, classname=cls.__name__
        )

class HackintYa(YouTubeService):
    """
    Queries #youtubearchive for the video you requested.
    """
    name = methods["hackint_ya"]["title"]
    note = ("Video retrieval is currently not available for technical reasons. "
            "Check back later for access instructions. This may take weeks or months."
            )
    configId = "hackint_ya"

    @classmethod
    async def _run(cls, id, session: aiohttp.ClientSession):
        username: str = methods[cls.configId]["username"]
        password: str = methods[cls.configId]["password"]
        excluded: list[str] = methods[cls.configId].get("excluded", [])

        vid = id
        auth = aiohttp.BasicAuth(username, password)
        comments = False
        async with session.get("https://ya.borg.xyz/cgi-bin/capture-count?v=" + vid, auth=auth, timeout=10) as resp:
            count = await resp.text()
        if not count:
            raise ValueError("Server returned empty response!")
        count = int(count)
        async with session.get("https://ya.borg.xyz/cgi-bin/capture-comment-counts?v=" + vid, auth=auth, timeout=10) as resp:
            commentcount = await resp.text()
        archived = (count > 0)
        comments = [i for i in commentcount.split("\n") if i.strip("∅\n") and i.strip() != "0"]
        rawraw = (count, commentcount)
        if vid in excluded:
            return cls(
                archived=False, capcount=0, comments=False, lastupdated=time.time(), name=cls.getName(),
                note="", rawraw=(0, ""), metaonly=False, classname=cls.__name__
            )
        return cls(
            archived=archived, capcount=count, comments=(len(comments) > 0), lastupdated=time.time(), name=cls.getName(),
            note=cls.note if archived else "", rawraw=rawraw, metaonly=False, classname=cls.__name__
        )


class DistributedYoutubeArchive(YouTubeService):
    """
    Queries DYA for the video in question.
    """
    name = methods['distributed_youtube_archive']['title']
    configId = "distributed_youtube_archive"

    @classmethod
    async def _run(cls, id, session: aiohttp.ClientSession):
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
        note = "One or more contributors to the Distributed YouTube Archive have the video. Join their Discord server by clicking the link and ask for help." if archived else ""
        metaonly = False
        comments = None # we can't tell whether there are comments or not
        available = "https://discord.gg/ZvzyRWTujK" if archived else None
        return cls(
            archived=archived, capcount=capcount, lastupdated=lastupdated,
            name=cls.getName(), note=note, rawraw=j, metaonly=metaonly,
            comments=comments, available=available, classname=cls.__name__
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
        urls_to_try = ("https://hobune.stream/videos/{}", "https://hobune.stream/tpa-h/videos/{}")
        raw = []
        archived = False
        available = None
        lastupdated = time.time()
        cls.lastretrieved = lastupdated
        for url in urls_to_try:
            url = url.format(id)
            async with session.head(url, timeout=5) as resp:
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
            rawraw=raw, metaonly=False, comments=False, available=available, classname=cls.__name__
        )

class removededm(YouTubeService):
    """
    Queries the removed.edm database for the video you requested.
    """
    name = methods["removededm"]["title"]
    configId = "removededm"

    @classmethod
    async def _run(cls, id, session: aiohttp.ClientSession) -> typing.Self:
        ismeta = False
        # Note: Video IDs starting with an underscore are redirected to have a period at the start due to
        #       limitations in the wiki software
        potential_links = (f"https://removededm.com/File:{id}.mp4", f"https://removededm.com/File:{id}.webm")
        archived = False # not technically necessary but makes linters happy
        rawraw = None
        lien = None
        for lnk in potential_links:
            async with session.head(lnk, timeout=15, allow_redirects=True) as response:
                archived = response.status == 200 # if there's a redirect, it's archived
                rawraw = response.status
                if archived:
                    # No more searching needed, it's archived
                    lien = lnk
                    break
        if not archived:
            link = f"https://removededm.com/{id}"
            async with session.head(link, timeout=15, allow_redirects=True) as response:
                archived = response.status == 200
                if archived:
                    lien = link
                    ismeta = True
                rawraw = response.status

        return cls(
            archived=archived, rawraw=rawraw, available=lien, metaonly=ismeta, comments=False,
            capcount=(1 if archived else 0), error=None, lastupdated=time.time(),
            name=cls.getName(), note="", classname=cls.__name__
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
    async def _run(cls, id, session: aiohttp.ClientSession) -> typing.Self:
        key = methods[cls.configId]["api_key"]

        while time.time() - cls.lastretrieved < cls.cooldown:
            await asyncio.sleep(0.1)
        lastupdated = time.time()
        cls.lastretrieved = int(time.time())
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
                available=available, classname=cls.__name__
        )

class Playboard(YouTubeService):
    """
    Queries Playboard.co for whether it's archived or not.
    Playboard is metadata-only as far as I know.
    """
    name = methods["playboard_co"]["title"]
    note = "The Playboard scraper is unreliable; please verify values yourself."
    configId = "playboard_co"
    user_agent = methods["playboard_co"]["user_agent"]

    @classmethod
    async def _run(cls, id, session: aiohttp.ClientSession) -> typing.Self:
        note = cls.note
        user_agent = cls.user_agent % random.randint(0, 100)
        url = f"https://playboard.co/en/video/{id}"
        async with session.get(url, headers={"User-Agent": user_agent}) as resp:
            code = resp.status
        rawraw = {"status_code": code, "ua_used": user_agent}
        lastupdated = time.time()
        available = None
        if code == 200:
            archived = True
            available = url
        elif code == 429:
            archived = False
            note = "You have been rate-limited by Playboard."
        elif code == 404:
            archived = False
        else:
            raise AssertionError(f"bad status code {code}")
        return cls(
                archived=archived, capcount=1 if archived else 0,
                lastupdated=lastupdated, name=cls.getName(), note=note,
                rawraw=rawraw, metaonly=True, comments=False,
                available=available, classname=cls.__name__
        )

class AltCensored(YouTubeService):
    """
    Queries altCensored for whether it's archived or not.
    altCensored does not store any videos. Instead, it links to archived versions.
    """
    name = methods["altcensored"]["title"]
    note = ""
    configId = "altcensored"

    @classmethod
    async def _run(cls, id, session: aiohttp.ClientSession) -> typing.Self:
        url = f"https://altcensored.com/watch?v={id}"
        async with session.get(url) as resp:
            code = resp.status
        lastupdated = time.time()
        available = None
        if code == 200:
            archived = True
            available = url
        elif code == 404:
            archived = False
        else:
            raise AssertionError(f"bad status code {code}")
        return cls(
                archived=archived, capcount=1 if archived else 0,
                lastupdated=lastupdated, name=cls.getName(), note=cls.note,
                rawraw=None, comments=False, available=available,
                metaonly=False, classname=cls.__name__
        )

class Odysee(YouTubeService):
    """
    Queries the LBRY YouTube Sync API to find out whether the video has been mirrored to Odysee.
    """
    name = methods['odysee']['title']
    configId = "odysee"

    @classmethod
    async def _run(cls, id, session: aiohttp.ClientSession):
        lastupdated = time.time()
        async with session.get(f"https://api.lbry.com/yt/resolve?video_ids={id}") as resp:
            status = resp.status
            if status != 200:
                raise RuntimeError(f"LBRY API returned bad status code {status}")
            j = await resp.json()
        if len(j) == 0: # pylint: disable=simplifiable-if-statement
            raise ValueError("Server returned empty response!")
        if "data" not in j:
            raise ValueError("No \"data\" field in response!")
        if "videos" not in j["data"]:
            raise ValueError("No \"videos\" field in response!")
        if id not in j["data"]["videos"]:
            raise ValueError("No video ID field in response!")
        odyseeId = j["data"]["videos"][id]
        if odyseeId is None:
            archived = False
            available = None
        else:
            odyseeLinkId = odyseeId.replace("#", ":")
            archived = True
            available = f"https://odysee.com/{odyseeLinkId}"
        return cls(
            archived=archived, capcount=1, lastupdated=lastupdated,
            name=cls.getName(), note="", rawraw=j, metaonly=False,
            comments=False, available=available, classname=cls.__name__
        )

class PreserveTube(YouTubeService):
    """
    Queries PreserveTube for whether it's archived or not.
    """
    name = methods["preservetube"]["title"]
    note = ""
    configId = "preservetube"

    @classmethod
    async def _run(cls, id, session: aiohttp.ClientSession) -> typing.Self:
        url = f"https://api.preservetube.com/video/{id}"

        # keep any pre-existing headers but patch in "Accept"
        headers = session.headers.copy()
        headers.update({"Accept": "application/json"})

        async with session.get(url, headers=headers) as resp:
            json = await resp.json()
        lastupdated = time.time()
        available = None
        if e := json.get("error"):
            if e == "404":
                archived = False
            else:
                raise RuntimeError("Unexpected error field")
        else:
            assert "title" in json
            archived = True
            available = f"https://preservetube.com/watch?v={id}"
        return cls(
                archived=archived, capcount=1 if archived else 0,
                lastupdated=lastupdated, name=cls.getName(), note=cls.note,
                rawraw=None, comments=False, available=available,
                metaonly=False, classname=cls.__name__
        )

class NyaneOnline(YouTubeService):
    name = methods['nyaneonline']['title']
    note = ""
    configId = "nyaneonline"

    @classmethod
    async def _run(cls, id, session: aiohttp.ClientSession) -> typing.Self:
        url = f"https://www.nyane.online/video"

        async with session.head(url, params={"id": id}) as resp:
            lastupdated = time.time()
            status = resp.status
            if status == 200:
                archived = True
                available = str(resp.request_info.url)
            elif status == 404:
                archived = False
                available = None
            else:
                raise AssertionError(f"bad status code {status}")

        return cls(archived=archived, capcount=1 if archived else 0,
                   lastupdated=lastupdated, name=cls.getName(), note=cls.note,
                   rawraw=None, comments=False, available=available,
                   metaonly=False, classname=cls.__name__
        )
