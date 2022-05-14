from api_client import ApiClient
from utils import ChapterSelection
from asyncio import run
from pathlib import Path
import logging
import click
from configuration_file import Configuration

chapter_help = """
A list separated by comma, of chapter number or range (start-end)
ex : 1,3,4-10
by default select all chapters
"""


def get_uuid(url: str) -> str:
    for part in url.split('/'):
        if "-" in part:
            return part


async def main(uuid, chapter_selection, configuration):
    client = ApiClient(uuid, chapter_selection, configuration)
    await client.dowload_manga()
    await client.close()


@click.command()
@click.option("-l", "--language", default=None, help="A list of languages separated by comma ordered by desc priority")
@click.option("-o", "--output", default=None)
@click.option("--cbz/--no-cbz", default=None)
@click.option("-c", "--chapters", default=None, help=chapter_help)
@click.option("--config", default=False, is_flag=True)
@click.argument("url")
def cli(language, output, cbz, chapters, url, config):
    if config:
        Configuration.open()
        return

    configuration = Configuration.load()
    # override configuration with arguments
    if language is not None:
        configuration.languages = language.split(",")
    if output is not None:
        configuration.output_directory = output
    if cbz is not None:
        configuration.is_cbz = cbz

    uuid = get_uuid(url)
    chapter_selection = ChapterSelection.all() if chapters is None else ChapterSelection.parse(chapters)

    logging.basicConfig(level=logging.DEBUG)
    run(main(uuid, chapter_selection, configuration))


if __name__ == "__main__":
    cli()
