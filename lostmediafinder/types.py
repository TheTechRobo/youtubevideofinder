from snscrape.base import _JSONDataclass as JSONDataclass

import asyncio as aio
import cachetools.func
import dataclasses
import time
import typing
import re
import urllib.parse

import nest_asyncio
nest_asyncio.apply()


T = typing.TypeVar("T", bound="Service")

@dataclasses.dataclass
class Service(JSONDataclass):
    """
    The data parsed out of the server.

    Attributes:
        archived (bool): Whether the video is archived or not.
        available (int): A link to the archived material if it can be produced; null otherwise.
        capcount (int): The number of captures. Currently deprecated - the capture count sent may or may not be the true number of captures. However, it will always be a positive non-zero number if the video is archived.
        error (bool): Whether or not the request failed.
        lastupdated (int): The timestamp the data was retrieved from the server. Used internally to expire cache entries.
        name (str): The name of the service. Used in the UI.
        note (str): A footnote about the service. This could be different depending on conditions. For example, the Internet Archive has an extra passage if the item is dark. Used in the UI.
        rawraw (Any): The data used to check whether the video is archived on that particular service. For example, for GhostArchive, it would be the HTTP status code.
        metaonly (bool): True if only the metadata is archived. This value should not be relied on!
        comments (bool): True if the comments are archived. This value should not be relied on!
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
    error: bool = False

    @classmethod
    def _run(cls, id) -> T:
        raise NotImplementedError("Subclass Service and impl the _run function")

    """
    Do not use this function!
    """
    @classmethod
    def Run(cls, id, includeRaw=True) -> T:
        try:
            return cls._run(id)
        except Exception as ename:
            note = f"An error occured while retrieving data from {cls.getName()}."
            print(ename)
            return cls(
                    archived=False, capcount=0, error=True,
                    lastupdated=time.time(), name=cls.getName(), note=note,
                    rawraw=str(ename), metaonly=False, comments=False,
                    available=None
            )

    """
    Retrieves the data from the service.
    Arguments:
        id (str): The video ID.
        includeRaw (bool): Whether or not to include the raw data as sent from the service. If you don't need this data, turn this off; it's only the default for compatibility.
    """
    @classmethod
    # cache has a max of 128 items; items are cached for 600 seconds (10min)
    # important settings:
    #   maxsize=128, ttl=600
    # might add this to config.py later
    @cachetools.func.ttl_cache
    def run(cls, id: str, includeRaw=True):
        return cls.Run(id, includeRaw)

    """
    Runs cls.run(...) but it's async.
    """
    @classmethod
    async def runAsync(cls, id, includeRaw=True):
        return cls.run(id, includeRaw)

    """
    Gets the name of the service.
    """
    @classmethod
    def getName(cls) -> str:
        return getattr(cls, "name", cls.__name__)

    def __str__(self):
        lien = f"\n  Link: {self.available}" if self.available else ""
        m = "(metadata only)" if self.metaonly else ""
        m = m + " (incl. comments)" if self.comments else m
        string = f"""- Service Name: {self.name}
  Archived? {self.archived} {m} {lien}
  \t{self.note.strip()}
"""
        return string

@dataclasses.dataclass
class Response(JSONDataclass):
    """
    A response from the server.

    Attributes:
        id (str): The interpreted video ID.
        status (str): bad.id if invalid ID.
        keys (list[Service]): An array with all the server responses. THIS IS DIFFERENT THAN BEFORE! Before, this would be an array of strings. You'd use the strings as keys. Now, this array has the data directly!
        api_version (int): The API version. Currently set to %s. Breaking API changes are made by incrementing this. There may be a way to request a specific version in the future.
    """
    id: str
    status: str
    keys: list[Service]
    api_version: int = 2

    @classmethod
    def _get_services(cls):
        return Service.__subclasses__()

    """
    Runs all the Services.
    Arguments:
        id: The video ID
        asyncio: Whether or not to use asyncio.run_until_complete; this is implied if you use generateAsync
    """
    
    @classmethod
    def generate(cls, id, asyncio=False):
        if not re.match(r"^[A-Za-z0-9_-]{10}[AEIMQUYcgkosw048]$", id):
            return cls(status="bad.id", id=id, keys=[])
        keys = []
        services = cls._get_services()
        for subclass in services:
            data = None
            if asyncio:
                data = aio.get_event_loop().run_until_complete(subclass.runAsync(id))
            else:
                data = subclass.run(id)
            keys.append(data)
        return cls(id=id, status="ok", keys=keys)

    """
    Runs all the Services asynchronously.
    """
    @classmethod
    async def generateAsync(cls, *args, **kwargs):
        kwargs['asyncio'] = True
        return cls.generate(*args, **kwargs)

    def __str__(self):
        services = "Services:\n"
        for i in self.keys:
            services += str(i)
        string = f"""Video ID: {self.id}
{services}"""
        return string

Response.__doc__ = Response.__doc__.replace("%s", str(Response.api_version))
        