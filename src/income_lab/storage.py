from pathlib import Path
from urllib.parse import urlparse

import fsspec
import pandas as pd


def options(uri: str, endpoint: str) -> dict:
    if not uri.startswith("s3://"):
        return {}
    return {
        "client_kwargs": {"endpoint_url": endpoint} if endpoint else {},
        "config_kwargs": {"s3": {"addressing_style": "path"}},
    }


def ensure_bucket(uri: str, endpoint: str) -> None:
    if uri.startswith("s3://"):
        bucket = urlparse(uri).netloc
        fs = fsspec.filesystem("s3", **options(uri, endpoint))
        if not fs.exists(bucket):
            fs.mkdir(bucket)
    else:
        Path(uri).mkdir(parents=True, exist_ok=True)


def read_frame(uri: str, endpoint: str) -> pd.DataFrame:
    return pd.read_parquet(uri, storage_options=options(uri, endpoint) or None)


def write_frame(frame: pd.DataFrame, uri: str, endpoint: str) -> None:
    if not uri.startswith("s3://"):
        Path(uri).parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(uri, index=False, storage_options=options(uri, endpoint) or None)
