import logging
import asyncio
import shutil

from typing import Optional, Dict, List, Iterable
from aiohttp import ClientSession, TCPConnector, ClientPayloadError, ClientTimeout
from utils import safe, RateLimiter, standard_chapter_number, DomainRateLimiter
from pathlib import Path
from zipfile import ZipFile, ZIP_STORED


class Urls:
    ROOT = "https://api.mangadex.org"
    MANGA = ROOT + "/" "manga"
    CHAPTER = "https://api.mangadex.org/at-home/server"


class ApiClient(object):
    quality = "data"

    def __init__(self, uuid, language, output_dir, to_cbz=False):
        self.uuid = uuid
        self.language = language
        # don't re-use the same connections because the server can close the connection before we are done wiht it
        # since we are limited on the number of request this shoudln't be an issue for performances
        connector = TCPConnector(force_close=True)
        timeout = ClientTimeout(total=60 * 60)
        self.session = DomainRateLimiter(ClientSession(connector=connector, timeout=timeout))
        self.output_dir = Path(output_dir)
        self.to_cbz = to_cbz

    async def close(self):
        await self.session.close()

    @safe
    async def get_title(self) -> Optional[str]:
        url = Urls.MANGA + "/" + self.uuid
        logging.debug(f"get_title : {url}")
        title = None
        async with await self.session.get(url) as response:
            if response.status != 200:
                return title
            try:
                data = await response.json()
                title = data["data"]["attributes"]["title"][self.language]
            except KeyError:  # if no manga title in requested dl language
                try:
                    # lookup in altTitles
                    alt_titles = {}
                    titles = data["data"]["attributes"]["altTitles"]
                    for val in titles:
                        alt_titles.update(val)
                    title = alt_titles[self.language]
                except:
                    # fallback to English title
                    try:
                        title = data["data"]["attributes"]["title"]["en"]
                    except Exception as ex:
                        logging.error(f"Couldn't retrieve manga title : {ex}")
            return title

    @safe
    async def get_chapters(self) -> Optional[Iterable[tuple[int, str]]]:
        url = Urls.MANGA + f"/{self.uuid}/feed"
        logging.debug(f"get_chapters : {url}")
        params = f"?translatedLanguage[]={self.language}&limit=0"
        url += params
        async with await self.session.get(url) as response:
            if response.status != 200:
                logging.error(f"Failed to retrieved chapter with url {url} and status : {response.status}")
                return None
            data = await response.json()
            total = data["total"]
            offset = 0
            result = []
            while offset < total:
                bulk = await self._get_chapter_bulk(offset)
                result += bulk
                offset += 500

            return result

    @staticmethod
    def _extract_chapter_info(data):
        result = []
        for infos in data["data"]:
            if infos["type"] != "chapter":
                continue
            chapter = infos["attributes"]["chapter"]
            chapter = standard_chapter_number(chapter)
            chapter_uid = infos["id"]
            if int(infos["attributes"]["pages"]) != 0:
                result.append((chapter, chapter_uid))
        return result

    async def _get_chapter_bulk(self, offset):
        url = f"{Urls.MANGA}/{self.uuid}/feed?order[chapter]=asc&order[volume]=asc&limit=500" \
              f"&translatedLanguage[]={self.language}&offset={offset}"
        async with await self.session.get(url) as response:
            if response.status != 200:
                logging.error(f"failed to get chapter bulk with url {url}")
                return None
            data = await response.json()
            return ApiClient._extract_chapter_info(data)

    async def dowload_manga(self):
        title = await self.get_title()
        manga_dir = self.output_dir / title
        manga_dir.mkdir(exist_ok=True)
        chapters = await self.get_chapters()
        if chapters is None:
            return None
        await asyncio.gather(
            *[self.download_chapter(uuid, manga_dir / f"{chapter}_{title}") for (chapter, uuid) in chapters])

    async def download_chapter(self, chapter_uuid: str, chapter_folder):
        if chapter_folder.exists():
            # handle duplicates
            chapter_folder = chapter_folder.parent / (chapter_folder.name + "_1")
        chapter_folder.mkdir(exist_ok=True)
        destination = chapter_folder.name
        urls = await self.get_page_infos(chapter_uuid)
        if urls is None:
            return None

        await self.bulk_download(urls, chapter_folder)
        if self.to_cbz:
            filename = chapter_folder.parent / f"{destination}.cbz"
            with ZipFile(filename, "w", ZIP_STORED) as cbz_file:
                for file in chapter_folder.glob("*"):
                    cbz_file.write(file, file)
            shutil.rmtree(chapter_folder)

    @safe
    async def get_page_infos(self, chapter_uuid: str, nb_retry=3) -> Optional[Iterable[str]]:
        if nb_retry <= 0:
            return None

        url = Urls.CHAPTER + "/" + chapter_uuid
        async with await self.session.get(url) as response:
            self.session.register_limit(url, response.headers)
            if response.status != 200:
                logging.error(f"Failted to retrieve page info with url {url} and status {response.status}")
                if response.status == 429:
                    self.session.register_too_many_request(url, response.headers)
                    return await self.get_page_infos(chapter_uuid, nb_retry - 1)
                return None

            data = await response.json()
            base_url = data["baseUrl"]
            chapter_hash = data["chapter"]["hash"]
            result = []
            for page_filename in data["chapter"][ApiClient.quality]:
                result.append(f"{base_url}/data/{chapter_hash}/{page_filename}")
            return result

    async def download_page(self, url: str, chapter_folder: str, nb_retry=3):
        if nb_retry <= 0:
            return

        async with await self.session.get(url) as response:
            if response.status != 200:
                logging.error(f"Failed to retrieved : {url} with status : {response.status}")
                if response.status == 429:
                    pass
            try:
                data = await response.content.read()
            except ClientPayloadError:
                await self.download_page(url, chapter_folder, nb_retry - 1)
                return

            fname = chapter_folder / url.split("/")[-1]
            with open(fname.absolute(), "wb") as f:
                f.write(data)

    async def bulk_download(self, urls: Iterable[str], destination: str):
        return await asyncio.gather(*[self.download_page(url, destination) for url in urls])
