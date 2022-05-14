from dataclasses import dataclass
from utils import get_datadir, open_with_default_application
from pathlib import Path
import json


@dataclass(frozen=True)
class Configuration:
    languages: tuple = ("en",)
    output_directory: str = str(Path.home() / "Downloads")
    is_cbz: bool = True
    download_duplicates = False

    def to_json(self) -> str:
        return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, indent=4)

    @property
    def output_path(self):
        return Path(self.output_directory)

    @staticmethod
    def path():
        return get_datadir() / "mangadex_dl" / "configuration.json"

    @classmethod
    def load(cls):
        path = Configuration.path()
        if not path.exists():
            configuration = cls()
            configuration.save()
            return configuration
        with path.open("r") as f:
            fields = json.load(f)
            return cls(**fields)

    def save(self):
        path = Configuration.path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w") as f:
            f.write(self.to_json())

    @staticmethod
    def open():
        if not Configuration.path().exists():
            Configuration().save()
        open_with_default_application(str(Configuration.path()))
