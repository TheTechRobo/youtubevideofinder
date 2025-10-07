"""
All the Service implementations live here.
"""

import random, time, aiohttp, asyncio
import typing_extensions as typing
from .types import Link, LinkContains, YouTubeService, methods, experiment_base_url
from yarl import URL

async def submit_experiment(session: aiohttp.ClientSession, experiment_name: str, video_id: str, **report):
    if experiment_base_url:
        report |= {
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
    async def _run(cls, id, session: aiohttp.ClientSession):
        lien = f"https://i.ytimg.com/vi/{id}/hqdefault.jpg"
        async with session.head(lien, allow_redirects=False, timeout=15) as response:
            code = response.status

        rawraw = code
        archived = None
        link = f"https://youtu.be/{id}"

        if code == 200:
            archived = True
            yield Link(
                url = link,
                contains = LinkContains(True, True, True, True, True),
                title = "Watch page"
            )
            yield Link(
                url = lien,
                contains = LinkContains(thumbnail = True),
                title = "Thumbnail"
            )
        else:
            archived = False

        lastupdated = time.time()
        yield cls(
            archived=archived, lastupdated=lastupdated, name=cls.getName(), note="", rawraw=rawraw,
            metaonly=False, classname=cls.__name__
        )


class WaybackMachine(YouTubeService):
    name = methods["ia_wayback"]["title"]
    configId = "ia_wayback"

    @classmethod
    async def _run(cls, id: str, session: aiohttp.ClientSession):
        ismeta = False
        archived = False

        params = {"vtype": "youtube", "vid": id}
        async with session.get("https://web.archive.org/__wb/videoinfo", params=params, timeout=5) as response:
            viresp = await response.json()
            videoinfo_archived = bool(viresp.get("formats"))
            if videoinfo_archived:
                archived = True
                formats = viresp['formats']
                for format in formats:
                    url, ts = format['url'], format['timestamp']
                    lien = f"https://web.archive.org/web/{ts}/{url}"
                    mimetype = format['mimetype']
                    m_type, m_format = mimetype.split("/", 1)
                    if m_type == "video":
                        title = f"Video ({m_format})"
                        contains = LinkContains(
                            video = True,
                            standalone_video = True
                        )
                    elif m_type == "audio":
                        title = f"Audio ({m_format})"
                        contains = LinkContains(
                            standalone_audio = True
                        )
                    else:
                        title = mimetype
                        contains = LinkContains(
                            video = True,
                            standalone_video = True,
                            standalone_audio = True
                        )
                    yield Link(
                        url = lien,
                        contains = contains,
                        title = title,
                    )

        if not archived:
            lien = f"https://web.archive.org/web/0id_/http://wayback-fakeurl.archive.org/yt/{id}"
            async with session.head(lien, allow_redirects=False, timeout=15) as response:
                redirect = response.headers.get("location")
                archived = bool(redirect)
                if redirect:
                    assert URL(redirect) != "/sry", "Redirected to sorry page. Is IA down?"
                fakeurl_archived = archived
                if fakeurl_archived:
                    yield Link(
                        url = lien,
                        contains = LinkContains(video = True, standalone_video = True),
                        title = "Video",
                        note = "A backup endpoint was used. More formats may be available later.",
                    )
                    await submit_experiment(session, "wb-vi-failures", id, fakeurl=fakeurl_archived, videoinfo=videoinfo_archived, viresp=viresp)

        response2 = None
        url_formats = [
            f"youtube.com/watch?v={id}",
            f"youtube.com/embed/{id}",
            f"youtube.com/shorts/{id}",
            f"youtu.be/{id}"
        ]

        # CDX above Availability because currently, latter will return text/html MIME type,
        # which causes the script to unalive itself, prematurely
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
                        yield Link(
                            url = lien,
                            contains = LinkContains(metadata = True),
                            title = "Watch page (may not work)"
                        )
                        if not archived:
                            ismeta = True
                        archived = True
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

        rawraw = (None, viresp, response2)
        yield cls(
            archived=archived, rawraw=rawraw,
            lastupdated=time.time(), name=cls.getName(), note="", metaonly=ismeta,
            classname=cls.__name__
        )


class ArchiveOrgDetails(YouTubeService):
    name = methods["ia_details"]["title"]
    configId = "ia_details"
    items_tried = [
        "youtube-%s",
        "youtube_%s",
        "%s"
    ]

    @classmethod
    async def _run(cls, id, session: aiohttp.ClientSession):
        responses = []
        is_dark = False
        archived = False
        for template in cls.items_tried:
            ident = template % id
            async with session.get(f"https://archive.org/metadata/{ident}", timeout=12) as resp:
                metadata = await resp.json()
            responses.append(metadata)
            if metadata.get("is_dark"):
                is_dark = True
            if metadata and (not metadata.get("is_dark")):
                is_dark = False
                archived = True
                yield Link(
                    url = f"https://archive.org/details/{ident}",
                    # We don't know what it has, so assume it has everything
                    contains = LinkContains(True, True, True, True, True),
                    title = "Item"
                )
        rawraw = responses
        note = ""

        # Helper source code is at endpoint /source_code
        helper_url = f"https://fyt-helper.thetechrobo.ca/ia_extra/{id}"
        async with session.get(helper_url) as resp:
            if resp.status == 200:
                archived = True
                j = await resp.json()
                lien = f"https://archive.org/details/{j['item']}"
                lnote = "This is a generic channel item. It may contain multiple videos."
                yield Link(
                    url = lien,
                    contains = LinkContains(True, True, True, True, True),
                    title = "Item",
                    note = lnote,
                )
            elif resp.status == 404:
                pass
            else:
                raise AssertionError("fyt-helper check failed")

        if not archived:
            note = "Even if it isn't found here, it might still be in the Internet Archive. This site only checks for certain item identifiers."
            if is_dark:
                note = "An item was found, but it is currently unavailable to the general public.<br>" + note
        yield cls(
            archived=archived, lastupdated=time.time(), name=cls.getName(), note=note,
            rawraw=rawraw, metaonly=False, classname=cls.__name__
        )


class ArchiveOrgCDX(YouTubeService):
    """
    Queries the Archive.org CDX for an archived video thumb
    """
    name = methods["ia_cdx"]["title"]
    configId = "ia_cdx"

    @classmethod
    async def _run(cls, id, session: aiohttp.ClientSession):
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

        archived = False
        # Limit to one result
        # TODO: maybe add a note about this?
        for result in results[:1]:
            yield Link(
                url = f"https://web.archive.org/web/{result[1]}/{result[2]}",
                contains = LinkContains(thumbnail = True),
                title = "Thumbnail",
            )
            archived = True

        yield cls(
                archived=archived, rawraw=None,
                lastupdated=time.time(), name=cls.getName(),
                note="", metaonly=True, classname=cls.__name__
        )


class GhostArchive(YouTubeService):
    name = methods["ghostarchive"]["title"]
    configId = "ghostarchive"

    @classmethod
    async def _run(cls, id, session: aiohttp.ClientSession):
        link = f"https://ghostarchive.org/varchive/{id}"
        async with session.get(link, timeout=5) as resp:
            code = resp.status
            ct = await resp.text()
        rawraw = code
        archived = None
        match code:
            case 200:
                archived = True
                assert "Visit the main page" in ct
                yield Link(
                    url = link,
                    contains = LinkContains(video = True, metadata = True),
                    title = "Video"
                )
            case 404:
                archived = False
            case 500:
                archived = False
            case _:
                raise AssertionError(f"bad status code (expected one of (200, 404, 500), got {code})")
        lastupdated = time.time()
        yield cls(
            archived=archived, lastupdated=lastupdated, name=cls.getName(), note="", rawraw=rawraw,
            metaonly=False, classname=cls.__name__
        )

class HackintYa(YouTubeService):
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
            yield cls(
                archived=False, lastupdated=time.time(), name=cls.getName(),
                note="", rawraw=(0, ""), metaonly=False, classname=cls.__name__
            )
        yield cls(
            archived=archived, comments=(len(comments) > 0), lastupdated=time.time(), name=cls.getName(),
            note=cls.note if archived else "", rawraw=rawraw, metaonly=False, classname=cls.__name__
        )


class DistributedYoutubeArchive(YouTubeService):
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
                yield Link(
                    url = "https://discord.gg/ZvzyRWTujK",
                    contains = LinkContains(True, True, True, True, True),
                    title = "Discord invite",
                )
        metaonly = False
        note = (
            "One or more contributors to the Distributed YouTube Archive have the video. "
            "Join their Discord server to request retrieval."
        ) if archived else ""
        yield cls(
            archived=archived, lastupdated=lastupdated,
            name=cls.getName(), note=note, rawraw=j, metaonly=metaonly,
            classname=cls.__name__
        )

class Hobune(YouTubeService):
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
        lastupdated = time.time()
        cls.lastretrieved = lastupdated

        for url in urls_to_try:
            url = url.format(id)
            async with session.head(url, timeout=5) as resp:
                code = resp.status
                raw.append(code)
            if code == 200:
                archived = True
                yield Link(
                    url = url,
                    contains = LinkContains(video = True, metadata = True, thumbnail = True),
                    title = "Video"
                )
            elif code != 404:
                raise RuntimeError("Hobune.stream returned invalid status code %s" % code)

        yield cls(
            archived=archived, lastupdated=lastupdated, name=cls.getName(), note="",
            rawraw=raw, metaonly=False, classname=cls.__name__
        )

class removededm(YouTubeService):
    name = methods["removededm"]["title"]
    configId = "removededm"

    @classmethod
    async def _run(cls, id, session: aiohttp.ClientSession):
        got_video = False
        # Note: Video IDs starting with an underscore are redirected to have a period at the start due to
        #       limitations in the wiki software
        potential_video_links = (f"https://removededm.com/File:{id}.mp4", f"https://removededm.com/File:{id}.webm")
        potential_image_extensions = ("jpg", "png", "webp")
        archived = False
        rawraw = None
        link = f"https://removededm.com/{id}"

        async with session.head(link, timeout=15, allow_redirects=True) as response:
            archived = response.status == 200
            if archived:
                yield Link(
                    url = link,
                    contains = LinkContains(metadata = True),
                    title = "Metadata"
                )
            rawraw = response.status

        for lnk in potential_video_links:
            async with session.head(lnk, timeout=15, allow_redirects=True) as response:
                is_archived = response.status == 200
                rawraw = response.status
                if is_archived:
                    got_video = True
                    archived = True
                    yield Link(
                        url = lnk,
                        contains = LinkContains(video = True),
                        title = "Video"
                    )

        for extension in potential_image_extensions:
            lnk = f"https://removededm.com/File:{id}.{extension}"
            async with session.head(lnk, timeout=15, allow_redirects=True) as response:
                is_archived = response.status == 200
                if is_archived:
                    archived = True
                    yield Link(
                        url = lnk,
                        contains = LinkContains(thumbnail = True),
                        title = "Thumbnail"
                    )
            # Sometimes, if the video itself isn't available, but they have a frame from it,
            # it'll be available here.
            frame_link = f"https://removededm.com/File:{id}_.{extension}"
            async with session.head(frame_link, timeout=15, allow_redirects=True) as response:
                is_archived = response.status == 200
                if is_archived:
                    archived = True
                    yield Link(
                        url = frame_link,
                        contains = LinkContains(single_frame = True),
                        title = "Frame",
                        note = "This is a single frame of the video.",
                    )

        yield cls(
            archived=archived, rawraw=rawraw, metaonly=not got_video,
            error=None, lastupdated=time.time(), name=cls.getName(), note="", classname=cls.__name__
        )

# TODO: Make a YouTubeServiceWithCooldown or something

class Filmot(YouTubeService):
    name = methods["filmot"]["title"]
    lastretrieved: int = 0
    cooldown: int = 2
    configId = "filmot"

    @classmethod
    async def _run(cls, id, session: aiohttp.ClientSession):
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
            yield Link(
                url = f"https://filmot.com/video/{id}",
                contains = LinkContains(metadata = True, captions = True),
                title = "Metadata",
            )
        else:
            archived = False
        yield cls(
                archived=archived, lastupdated=lastupdated,
                name=cls.getName(), note="",
                rawraw=rawraw, metaonly=True,
                classname=cls.__name__
        )

class Playboard(YouTubeService):
    """
    Playboard is metadata-only as far as I know.
    """
    name = methods["playboard_co"]["title"]
    note = "The Playboard scraper is unreliable; please verify values yourself."
    configId = "playboard_co"
    user_agent = methods["playboard_co"]["user_agent"]

    @classmethod
    async def _run(cls, id, session: aiohttp.ClientSession):
        note = cls.note
        user_agent = cls.user_agent % random.randint(0, 100)
        url = f"https://playboard.co/en/video/{id}"
        async with session.get(url, headers={"User-Agent": user_agent}) as resp:
            code = resp.status
        rawraw = {"status_code": code, "ua_used": user_agent}
        lastupdated = time.time()
        if code == 200:
            archived = True
            yield Link(
                url = url,
                contains = LinkContains(metadata = True),
                title = "Metadata"
            )
        elif code == 429:
            archived = False
            note = "You have been rate-limited by Playboard."
        elif code == 404:
            archived = False
        else:
            raise AssertionError(f"bad status code {code}")
        yield cls(
                archived=archived, lastupdated=lastupdated,
                name=cls.getName(), note=note,
                rawraw=rawraw, metaonly=True,
                classname=cls.__name__
        )

class AltCensored(YouTubeService):
    """
    altCensored does not store any videos. Instead, it links to archived versions.
    """
    name = methods["altcensored"]["title"]
    note = ""
    configId = "altcensored"

    @classmethod
    async def _run(cls, id, session: aiohttp.ClientSession):
        url = f"https://altcensored.com/watch?v={id}"
        async with session.get(url) as resp:
            code = resp.status
        lastupdated = time.time()
        if code == 200:
            archived = True
            yield Link(
                url = url,
                contains = LinkContains(video = True, metadata = True),
                title = "Video"
            )
        elif code == 404:
            archived = False
        else:
            raise AssertionError(f"bad status code {code}")
        yield cls(
                archived=archived, lastupdated=lastupdated,
                name=cls.getName(), note=cls.note,
                rawraw=None, metaonly=False, classname=cls.__name__
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
        else:
            odyseeLinkId = odyseeId.replace("#", ":")
            archived = True
            yield Link(
                url = f"https://odysee.com/{odyseeLinkId}",
                contains = LinkContains(True, True),
                title = "Video"
            )
        yield cls(
            archived=archived, lastupdated=lastupdated,
            name=cls.getName(), note="", rawraw=j, metaonly=False,
            classname=cls.__name__
        )

class PreserveTube(YouTubeService):
    name = methods["preservetube"]["title"]
    note = ""
    configId = "preservetube"

    @classmethod
    async def _run(cls, id, session: aiohttp.ClientSession):
        url = f"https://api.preservetube.com/video/{id}"

        # keep any pre-existing headers but patch in "Accept"
        headers = session.headers.copy()
        headers.update({"Accept": "application/json"})

        async with session.get(url, headers=headers) as resp:
            json = await resp.json()
        lastupdated = time.time()
        if e := json.get("error"):
            if e == "404":
                archived = False
            else:
                raise RuntimeError("Unexpected error field")
        else:
            assert "title" in json
            archived = True
            available = f"https://preservetube.com/watch?v={id}"
            yield Link(
                url = available,
                contains = LinkContains(video = True, thumbnail = True, metadata = True),
                title = "Video"
            )
        yield cls(
                archived=archived, lastupdated=lastupdated,
                name=cls.getName(), note=cls.note,
                rawraw=None, metaonly=False, classname=cls.__name__
        )

class NyaneOnline(YouTubeService):
    name = methods['nyaneonline']['title']
    note = ""
    configId = "nyaneonline"

    @classmethod
    async def _run(cls, id, session: aiohttp.ClientSession):
        url = f"https://www.nyane.online/video"

        async with session.head(url, params={"id": id}) as resp:
            lastupdated = time.time()
            status = resp.status
            if status == 200:
                archived = True
                available = str(resp.request_info.url)
                yield Link(
                    url = available,
                    contains = LinkContains(video = True, metadata = True, thumbnail = True),
                    title = "Video"
                )
            elif status == 404:
                archived = False
            else:
                raise AssertionError(f"bad status code {status}")

        yield cls(archived=archived, lastupdated=lastupdated,
                   name=cls.getName(), note=cls.note,
                   rawraw=None, metaonly=False, classname=cls.__name__
        )

class LetsPlayIndex(YouTubeService):
    name = methods['letsplayindex']['title']
    note = ""
    configId = "letsplayindex"

    @classmethod
    async def _run(cls, id, session: aiohttp.ClientSession):
        url = f"https://www.letsplayindex.com/video/x-{id}"
        archived = False

        try:
            async with session.head(url, timeout=15) as resp:
                lastupdated = time.time()
                status = resp.status
                if status == 301:
                    archived = True
                    available = str(resp.request_info.url)
                    yield Link(
                        url = available,
                        contains = LinkContains(video = True, metadata = True, thumbnail = True),
                        title = "Video"
                    )
                elif status == 404:
                    archived = False
        except (aiohttp.ClientError, asyncio.TimeoutError):
            archived = False
            lastupdated = time.time()
        
        yield cls(archived=archived, lastupdated=lastupdated,
                   name=cls.getName(), note=cls.note,
                   rawraw=None, metaonly=False, classname=cls.__name__
        )
