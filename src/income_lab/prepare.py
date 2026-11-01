import json

from income_lab.config import Settings
from income_lab.data import prepare
from income_lab.features import apply

if __name__ == "__main__":
    settings = Settings.from_env()
    print(json.dumps({**prepare(settings), **apply(settings)}, indent=2))
