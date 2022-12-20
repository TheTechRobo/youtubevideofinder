"""
The classes that are used to store the response data.
"""

import asyncio as aio
import dataclasses
import time
import typing
import re

import cachetools.func
import nest_asyncio

from snscrape.base import _JSONDataclass as JSONDataclass

import config
def update_cnfig(ya, filmot, version):
    """
    Updates the configuration for the #youtubearchive and Filmot services.

    Check lostmediafinder.config for documentation.
    """

    config.ya = ya
    config.filmot = filmot
    config.config_version = version

nest_asyncio.apply()

T = typing.TypeVar("T", bound="YouTubeService") # pylint: disable=invalid-name
# (this name is fine)

@dataclasses.dataclass
class Service(JSONDataclass):
    """
    The data parsed out of the server.

    Attributes:
        archived (bool): Whether the video is archived or not.
        available (Optional[str]): A link to the archived material if it can be produced; null otherwise.
        capcount (int): The number of captures. Currently deprecated - the capture count sent may or may not be the true number of captures. However, it will always be a positive non-zero number if the video is archived.
        error (Optional[str]): An error message if an error was encountered; otherwise, null.
        lastupdated (int): The timestamp the data was retrieved from the server. Used internally to expire cache entries.
        name (str): The name of the service. Used in the UI.
        note (str): A footnote about the service. This could be different depending on conditions. For example, the Internet Archive has an extra passage if the item is dark. Used in the UI.
        rawraw (Any): The data used to check whether the video is archived on that particular service. For example, for GhostArchive, it would be the HTTP status code.
        metaonly (bool): True if only the metadata is archived. This value should not be relied on!
        comments (bool): True if the comments are archived. This value should not be relied on!

        =Changelog=
        API VERSION 2 -> 3:
            - The `error` attribute is now no longer a boolean; it contains an error message if an error occured and null if no error occured
    """
    archived: bool
    capcount: int
    lastupdated: int
    name: str
    note: str
    rawraw: typing.Any
    metaonly: bool
    comments: bool

    available: typing.Optional[str] = None
    suppl: str = ""
    error: bool = None

    @staticmethod
    def _getFromConfig(key, key1=None):
        val = getattr(config, key)
        if key1:
            val = getattr(val, key1)
        return val

    @classmethod
    def _run(cls, id, includeRaw=True, asynchronous=False) -> T:
        raise NotImplementedError("Subclass Service and impl the _run function")

    @classmethod
    # cache has a max of 128 items; items are cached for 600 seconds (10min)
    # important settings:
    #   maxsize=128, ttl=600
    # might add this to config.py later
    @cachetools.func.ttl_cache
    def run(cls, id: str, includeRaw=True, **kwargs):
        """
        Retrieves the data from the service.
        Arguments:
            id (str): The video ID.
            includeRaw (bool): Whether or not to include the raw data as sent from the service. If you don't need this data, turn this off; it's only the default for compatibility.
        """
        try:
            return cls._run(id, includeRaw=includeRaw, **kwargs)
        except Exception as ename: # pylint: disable=broad-except
            note = f"An error occured while retrieving data from {cls.getName()}."
            print(ename)
            rawraw = f"{type(ename)}: {repr(ename)}"
            return cls(
                    archived=False, capcount=0, error=rawraw,
                    lastupdated=time.time(), name=cls.getName(), note=note,
                    rawraw=None, metaonly=False, comments=False,
                    available=None
            )

    @classmethod
    async def runAsync(cls, id, includeRaw=True):
        """
        Runs cls.run(...) but it's async.
        This currently still uses blocking networking (requests)!
        """
        return cls.run(id, includeRaw, asynchronous=True)

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
        return string

class YouTubeService(Service): # pylint: disable=abstract-method
    pass

@dataclasses.dataclass
class YouTubeResponse(JSONDataclass):
    """
    A response from the server.

    Attributes:
        id (str): The interpreted video ID.
        status (str): bad.id if invalid ID.
        keys (list[YouTubeService]): An array with all the server responses. THIS IS DIFFERENT THAN BEFORE! Before, this would be an array of strings. You'd use the strings as keys. Now, this array has the data directly!
        api_version (int): The API version. Breaking API changes are made by incrementing this.
    """
    id: str
    status: str
    keys: list[YouTubeService]
    api_version: int = 3

    def coerce_to_api_version(selfNEW, target):
        """
        Downgrades the API version to one of your choice, then returns it.

        Arguments:
            target (int): The target API version. Must be lower than self.api_version
        """
        import copy
        self = copy.deepcopy(selfNEW)
        currentApiVersion = self.api_version
        if currentApiVersion < target:
            raise ValueError("cannot upgrade api version")
        while self.api_version != target:
            fname = f"_convert_v{self.api_version}_to_v{self.api_version-1}"
            if not hasattr(self, fname):
                raise ValueError("cannot downgrade any further")
            self = getattr(self, fname)()
        assert self.api_version == target
        return self

    def _convert_v3_to_v2(selfNEW):
        import copy
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
    def _get_services(cls):
        return YouTubeService.__subclasses__()

    @staticmethod
    def verifyId(id: str) -> bool:
        """
        Checks if a video ID is valid.
        """
        return bool(re.match(r"^[A-Za-z0-9_-]{10}[AEIMQUYcgkosw048]$", id))

    @classmethod
    def generate(cls, id, asyncio=False):
        """
        Runs all the Services.
        Arguments:
            id: The video ID
            asyncio: Whether or not to use asyncio.run_until_complete; this is implied if you use generateAsync
        """
        if not cls.verifyId(id):
            return cls(status="bad.id", id=id, keys=[])
        keys = []
        services = cls._get_services()
        for subclass in services:
            result = None
            if asyncio:
                result = aio.get_event_loop().run_until_complete(subclass.runAsync(id))
            else:
                result = subclass.run(id)
            keys.append(result)
        return cls(id=id, status="ok", keys=keys)

    @classmethod
    async def generateAsync(cls, *args, **kwargs):
        """
        Runs all the Services asynchronously.
        """
        kwargs['asyncio'] = True
        return cls.generate(*args, **kwargs)

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
