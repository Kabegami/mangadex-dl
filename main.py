from api_client import ApiClient
from asyncio import run
from pathlib import Path
import logging
import click


def get_uuid(url: str) -> str:
    for part in url.split('/'):
        if "-" in part:
            return part


async def main(uuid, language, destination, to_cbz):
    client = ApiClient(uuid, language, destination, True)
    await client.dowload_manga()
    await client.close()


@click.command()
@click.option("-l", "--language", default='en')
@click.option("-o", "--output", default=None)
@click.option("--cbz/--no-cbz", default=True)
@click.argument("url")
def cli(language, output, cbz, url):
    uuid = get_uuid(url)
    destination = Path.home() / "download"
    if output is not None:
        destination = Path(output)
    logging.basicConfig(level=logging.DEBUG)
    run(main(uuid, language, destination, cbz))


if __name__ == "__main__":
    cli()
