"""
The classes that are used to store the response data.
"""
import copy
import dataclasses
import time
import typing_extensions as typing
import re

import asyncio
import aiohttp
import yaml

from snscrape.base import _JSONDataclass as JSONDataclass

with open('config.yml', 'r') as file:
    config_yml = yaml.safe_load(file)
    methods = config_yml["methods"]
    user_agent = config_yml.get("user_agent") # defaults to None if not set
    experiment_base_url = config_yml.get("experiment_base_url")
    if experiment_base_url:
        experiment_base_url = experiment_base_url.rstrip("/")

@dataclasses.dataclass
class Service(JSONDataclass):
    """
    The data parsed out of the server.

    Attributes:
        archived (bool): Whether the video is archived or not.
        available (list[Link]): Links to the archived material.
        error (Optional[str]): An error message if an error was encountered; otherwise, null.
        lastupdated (int): The timestamp the data was retrieved from the server.
        name (str): The name of the service. Used in the UI.
        note (str): A footnote about the service. This could be different depending on conditions. For example, the Internet Archive has an extra passage if the item is dark. Used in the UI.
        rawraw (Any): The data used to check whether the video is archived on that particular service. For example, for GhostArchive, it would be the HTTP status code. The structure could change at any time.
        metaonly (bool): True if only the metadata is archived. This value should not be relied on!
        comments (bool): True if the comments are archived. The meaning of False is undefined.
        maybe_paywalled (bool): True if the service might require payment.
        classname (str): The internal class name, useful for streaming mode.
    """
    archived: bool
    lastupdated: float
    name: str
    note: str
    rawraw: typing.Any
    metaonly: bool
    classname: str

    available: list["Link"] = dataclasses.field(default_factory=list)
    suppl: str = ""
    error: typing.Optional[typing.Any] = None
    maybe_paywalled: bool = False

    configId = None
    type: str = "service"
    comments: bool = False

    def __post_init__(self):
        if not self.comments:
            self.comments = any(map(lambda s : s.contains.comments, self.available))

    @classmethod
    async def _run(cls, id, session: aiohttp.ClientSession) -> typing.AsyncGenerator:
        raise NotImplementedError("Subclass Service and impl the _run function")
        yield 0 # exists for type checkers

    @classmethod
    def enabled(cls):
        configId = cls.configId
        serviceConfig = methods[configId]
        return serviceConfig['enabled']

    @classmethod
    async def run(cls, id: str, session: aiohttp.ClientSession, includeRaw=True, **kwargs):
        """
        Retrieves the data from the service.
        Arguments:
            id (str): The video ID.
            includeRaw (bool): Whether or not to include the raw data as sent from the service. If you don't need this data, turn this off; it's only the default for compatibility.
        """
        links = []
        try:
            async for i in cls._run(id, session, **kwargs):
                if isinstance(i, Link):
                    links.append(i)
                else:
                    if not includeRaw:
                        i.rawraw = None
                    i.available = links
                    i.__post_init__()
                yield i
        except Exception as ename: # pylint: disable=broad-except
            note = f"An error occured while retrieving data from {cls.getName()}."
            if "aiohttp" in str(type(ename)):
                # Ugly temporary hack
                rawraw = f"{type(ename)}"
            else:
                rawraw = f"{type(ename)}: {repr(ename)}"
            yield cls(
                    archived=any(map(lambda l : l.contains.comments, links)), error=rawraw,
                    lastupdated=time.time(), name=cls.getName(), note=note,
                    rawraw=None, metaonly=False,
                    available=links, classname=cls.__name__
            )

    @classmethod
    def getName(cls) -> str:
        """
        Gets the name of the service.
        """
        return getattr(cls, "name", cls.__name__)

    def __str__(self):
        lien = f"\n  Link: {self.available}" if self.available else ""
        meta = "(metadata only)" if self.metaonly else ""
        meta = meta + " (incl. comments)" if self.comments else meta
        string = f"""- Service Name: {self.name}
  Archived? {self.archived} {meta} {lien}
  \t{self.note.strip()}
"""
        if self.error:
            string += f"\t{self.error}\n"
        return string + "\n"

    def _5to4(self):
        service = copy.deepcopy(self)
        service.capcount = 1 if service.archived else 0
        if service.available:
            contains = service.available[0].contains
            service.metaonly = not contains.video
            service.comments = contains.comments
            service.available = service.available[0].url
        else:
            service.available = None
        return service

class YouTubeService(Service): # pylint: disable=abstract-method
    pass

class InvalidVideoIdError(ValueError):
    pass

class TargetAPIVersionTooLowError(ValueError):
    """
    Raised when `coerce_to_api_version` is called with an unsupported API version.
    """
    pass

class TargetAPIVersionTooHighError(ValueError):
    """
    Raised when `coerce_to_api_version` is called with an unsupported API version.
    """
    pass

# The current API version.
API_VERSION = 5

# Thin wrapper around a generator that allows us to define a `coerce_to_api_version` method,
# just like with the non-streaming response type.
class YouTubeStreamResponse:
    """
    A streamed response, as an iterable. It is not recommended to use the iterable directly;
    instead, write code around a specific API version and use `coerce_to_api_version` to ensure
    that you are using it.

    Note that when streaming, the minimum API version is 4.
    """
    api_version: int = API_VERSION

    # Initialises the iterator.
    # `gen` should be the generator
    def __init__(self, gen):
        self.gen = gen

    # Iterator Code
    def __aiter__(self):
        return self

    async def __anext__(self):
        return await anext(self.gen)

    def _convert_service_v5_to_v4(self, service):
        if isinstance(service, Service):
            return service._5to4()
        return service

    async def coerce_to_api_version(self, targetVersion):
        """
        Wraps the iterator, converting all messages to the target API version.
        The minimum version for streamed responses is 4.

        Note: If this function raises an exception other than TargetAPIVersionTooHighError or
        TargetAPIVersionTooLowError, the generator may be unusable and you should restart the process.
        """
        if targetVersion > self.api_version:
            raise TargetAPIVersionTooHighError(targetVersion)
        identity = lambda i : i
        # The function calls a direct current to target rather than current to current-1
        # because otherwise we can't be 100% sure that we can downgrade to the correct API version
        # and we can't "un-get" the item from the generator.
        if targetVersion != self.api_version:
            arrOfNamesFunction = getattr(self, f"_convert_narr_v{self.api_version}_to_v{targetVersion}", identity)
            serviceObjectFunction = getattr(self, f"_convert_service_v{self.api_version}_to_v{targetVersion}", identity)
            verdictObjectFunction = getattr(self, f"_convert_verdict_v{self.api_version}_to_v{targetVersion}", identity)
            if arrOfNamesFunction is identity and serviceObjectFunction is identity and verdictObjectFunction is identity:
                raise TargetAPIVersionTooLowError(targetVersion)
        else:
            # same as API version: do dumb wrappers
            arrOfNamesFunction = lambda a : a
            serviceObjectFunction = lambda a : a
            verdictObjectFunction = lambda a : a
        arrayOfNames = await anext(self.gen)
        yield arrOfNamesFunction(arrayOfNames)
        async for item in self.gen:
            if targetVersion == 4 and isinstance(item, Link):
                continue
            yield serviceObjectFunction(item)
            if item is None:
                break
        yield verdictObjectFunction(await anext(self.gen))


@dataclasses.dataclass
class LinkContains(JSONDataclass):
    video: bool = False
    metadata: bool = False
    comments: bool = False
    thumbnail: bool = False
    captions: bool = False

    standalone_video: bool = False
    """Just the video, no audio."""
    standalone_audio: bool = False
    """Just the audio, no video."""

    single_frame: bool = False
    """A single frame from the video."""


@dataclasses.dataclass
class Link(JSONDataclass):
    """
    A link. Returned in the available field on API v5 and up.

    Attributes:
        url (str): The URL.
        contains (LinkContains): What type of content the resource could contain. (Best effort.)
        title (str): The title (human-readable) of resource.
        note (Optional[str]): Any note about that particular resource.
    """
    url: str
    contains: LinkContains
    title: str

    note: typing.Optional[str] = None
    type: str = "link"
    classname: str = dataclasses.field(init = False)


@dataclasses.dataclass
class YouTubeResponse(JSONDataclass):
    """
    A response from the server.

    Attributes:
        id (str): The interpreted video ID.
        status (str): bad.id if invalid ID.
        keys (list[YouTubeService]): An array with all the server responses.
        api_version (int): The API version. Breaking API changes are made by incrementing this.
        verdict (dict): The verdict of the response. Has video, metaonly, and comments field, that are set to true if any archive was found where that was saved. Also has human_friendly field that has a simple verdict that can be used by people.
    """
    id: str
    status: str
    keys: list[YouTubeService]
    verdict: dict
    api_version: int = API_VERSION

    def coerce_to_api_version(selfNEW, targetVersion): # pylint: disable=no-self-argument
        """
        If necessary, downgrades the API version to one of your choice, then returns it.
        It is recommended to base your code around a specific API version and coerce it to that version.

        Arguments:
            targetVersion (int): The target API version. Must be lower than self.api_version

        Raises either TargetAPIVersionTooHighError or TargetAPIVersionTooLowError if the target is unsupported.
        """
        self = copy.deepcopy(selfNEW)
        currentApiVersion = self.api_version
        if currentApiVersion < targetVersion:
            raise TargetAPIVersionTooHighError("cannot upgrade api version")
        while self.api_version != targetVersion:
            fname = f"_convert_v{self.api_version}_to_v{self.api_version-1}"
            if not hasattr(self, fname):
                raise TargetAPIVersionTooLowError("cannot downgrade any further")
            self = getattr(self, fname)()
        assert self.api_version == targetVersion
        return self

    def _convert_v5_to_v4(selfNEW): # pylint: disable=no-self-argument
        self = copy.deepcopy(selfNEW)
        assert self.api_version == 5
        self.api_version = 4
        for i, service in enumerate(self.keys):
            self.keys[i] = service._5to4()
        return self

    # There were no changes to the data structure between v3 and v4
    def _convert_v4_to_v3(selfNEW): # pylint: disable=no-self-argument
        self = copy.deepcopy(selfNEW)
        assert self.api_version == 4
        self.api_version = 3
        return self

    def _convert_v3_to_v2(selfNEW): # pylint: disable=no-self-argument
        self = copy.deepcopy(selfNEW)
        assert self.api_version == 3
        self.api_version = 2
        for index, service in enumerate(self.keys):
            if service.error is None:
                service.error = False
            else:
                service.rawraw = service.error
                service.error = True
            self.keys[index] = service
        return self

    @classmethod
    def _get_services(cls) -> list['Service']:
        potentialServices = YouTubeService.__subclasses__()
        services = []
        for potentialService in potentialServices:
            if not potentialService.enabled():
                continue
            services.append(potentialService)
        return services

    @staticmethod
    def verifyId(id: str) -> bool:
        """
        Checks if a video ID is valid.
        """
        return bool(re.match(r"^[A-Za-z0-9_-]{10}[AEIMQUYcgkosw048]$", id))

    @staticmethod
    def create_verdict(archived: dict):
        verdict = ""
        if archived['video']:
            verdict += "Archived! "
        elif archived['metaonly']:
            verdict += "Archived with metadata only. "
        else:
            verdict += "Video not found. "
        if archived['comments']:
            verdict += "(with comments)"
        return verdict

    @classmethod
    async def _generateStream(cls, id: str, includeRaw=False):
        """
        Runs all the Services but as a generator.
        First item is a list of all the service names.
        Following that, all future items are service results.
        Then None will be provided to signal that all of the results have been sent.
        Finally, the last item is a dict containing the verdict.
        Arguments:
            id (str): The video ID
            includeRaw (bool): Whether or not to include the raw data in the `rawraw` field. If you don't need it, disable this.
        """
        if not cls.verifyId(id):
            raise InvalidVideoIdError(id)
        keys = []
        services = cls._get_services()
        coroutines = []
        headers = {}
        queue = asyncio.Queue(1)
        if user_agent:
            headers["User-Agent"] = user_agent
        done = asyncio.Event()

        async def iterate(name, gen):
            nonlocal taskCount
            try:
                async for i in gen:
                    if isinstance(i, Link):
                        i.classname = name
                    await queue.put(i)
            finally:
                taskCount -= 1
                if taskCount <= 0:
                    done.set()

        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20), headers=headers) as session:
            svcs = {}
            for service in services:
                svcs[service.__name__] = service.getName()
                coroutines.append((service.__name__, service.run(id, session, includeRaw=includeRaw)))
            taskCount = len(svcs)
            coroutines = [asyncio.create_task(iterate(name, coro)) for name, coro in coroutines]
            yield svcs

            while not done.is_set() or not queue.empty():
                done_task = asyncio.create_task(done.wait())
                queue_task = asyncio.create_task(queue.get())
                tasks = {done_task, queue_task}
                done_tasks, tasks = await asyncio.wait(tasks, return_when = asyncio.FIRST_COMPLETED)
                if queue_task in done_tasks:
                    retval = await queue_task
                    yield retval
                    if isinstance(retval, Service):
                        keys.append(retval)
                else:
                    queue_task.cancel()
                done_task.cancel()

            done_tasks, pending = await asyncio.wait(coroutines, timeout = 0)
            assert not pending
        yield None
        any_comments_archived = any(map(lambda e : e.comments, keys))
        any_metaonly_archived = any(map(lambda e : e.metaonly and e.archived, keys))
        any_videos_archived = any(map(lambda e : e.archived and not e.metaonly, keys))
        any_archived = {"video": any_videos_archived, "metaonly": any_metaonly_archived, "comments": any_comments_archived, "human_friendly": None}
        verdict = cls.create_verdict(any_archived)
        any_archived['human_friendly'] = verdict
        yield any_archived

    @classmethod
    async def generateStream(cls, id: str, includeRaw=False):
        gen = cls._generateStream(id, includeRaw=includeRaw)
        return YouTubeStreamResponse(gen)

    @classmethod
    async def generate(cls, id: str, includeRaw=False):
        generator = await cls.generateStream(id, includeRaw)
        # ignore the list of names as that is redundant in this case
        await anext(generator)
        results = []
        async for result in generator:
            if isinstance(result, Link):
                continue
            if result is None:
                # loop is over
                break
            results.append(result)
        any_archived = await anext(generator)
        return cls(id=id, status="ok", keys=results, verdict=any_archived)

    def __str__(self):
        services = "Services:\n"
        for i in self.keys:
            services += str(i)
        string = f"""Video ID: {self.id}
{services}"""
        return string

# TODO: Refactor Response a lot into a more generic thing,
# then make YouTubeResponse the same thing but specifying the keys
# and also specifying the subclasses to search

YouTubeResponse.__doc__ = YouTubeResponse.__doc__.replace("%s", str(YouTubeResponse.api_version))
