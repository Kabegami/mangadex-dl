from api_client import ApiClient
from utils import ChapterSelection
from asyncio import run
from pathlib import Path
import logging
import click

chapter_help = """
A list separated by comma, of chapter number or range (start-end)
ex : 1,3,4-10
by default select all chapters
"""


def get_uuid(url: str) -> str:
    for part in url.split('/'):
        if "-" in part:
            return part


async def main(uuid, language, destination, to_cbz, chapter_selection):
    client = ApiClient(uuid, language, destination,chapter_selection,  to_cbz)
    await client.dowload_manga()
    await client.close()


@click.command()
@click.option("-l", "--language", default='en')
@click.option("-o", "--output", default=None)
@click.option("--cbz/--no-cbz", default=True)
@click.option("-c", "--chapters", default=None, help=chapter_help)
@click.argument("url")
def cli(language, output, cbz, chapters, url):
    uuid = get_uuid(url)
    destination = Path.home() / "download"
    chapter_selection = ChapterSelection.all if chapters is None else ChapterSelection.parse(chapters)

    if output is not None:
        destination = Path(output)
    logging.basicConfig(level=logging.DEBUG)
    run(main(uuid, language, destination, cbz, chapter_selection))


if __name__ == "__main__":
    cli()
