from typing import NamedTuple
import yaml


class DB(NamedTuple):
    Name: str
    Host: str
    Port: int
    User: str
    Password: str

class Config(NamedTuple):
    MoodleToken: str
    MoodleUrl: str
    DB: DB


def load_config(config_path: str) -> Config:
    with open(config_path, mode="r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    try:
        return Config(
            MoodleToken=data["moodle"]["token"],
            MoodleUrl=data["moodle"]["company_url"],
            DB=DB(
                Name=data["database"]["name"],
                Password=data["database"]["password"],
                Host=data["database"]["host"],
                Port=data["database"]["port"],
                User=data["database"]["user"]
            )
        )
    except KeyError as err:
        exit(f"Проверьте в вашем конфиг-файле наличие ключа: {err}. Пример можете посмотреть в config.yaml.example")
