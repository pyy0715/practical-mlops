import hashlib
from io import BytesIO
from pathlib import Path
from urllib.request import urlopen

import pandas as pd
from sklearn.model_selection import train_test_split

from income_lab.config import Settings
from income_lab.storage import ensure_bucket, write_frame

UPSTREAM_COMMIT = "b67a8228336781c933dd68bb7dc520bd484c3371"
DATA_SHA256 = "2009995a1940d1a503a0ddb1997e63450e71a7fad013bcd7d1823d6e7693b6c4"
DATA_URL = (
    "https://raw.githubusercontent.com/practical-mlops/chapter-4/"
    f"{UPSTREAM_COMMIT}/data/income_data.csv"
)
GROUPS = {
    "demographic": ["Native_country", "Sex", "Race"],
    "relationship": ["Relationship", "Marital-Status"],
    "occupation": ["Workclass", "Education", "Occupation"],
}
SEED = 42
FEATURE_COLUMNS = [column for columns in GROUPS.values() for column in columns]
SNAPSHOT = f"datasets/{DATA_SHA256}"
SYNTHETIC_FEATURE_TIME = pd.Timestamp("2023-01-01T00:00:00Z")
SYNTHETIC_QUERY_TIME = pd.Timestamp("2023-01-02T00:00:00Z")


def load_data(cache: Path) -> pd.DataFrame:
    cache.parent.mkdir(parents=True, exist_ok=True)
    if not cache.exists():
        with urlopen(DATA_URL, timeout=60) as response:
            payload = response.read()
        if hashlib.sha256(payload).hexdigest() != DATA_SHA256:
            raise ValueError("Downloaded dataset checksum mismatch")
        cache.write_bytes(payload)
    payload = cache.read_bytes()
    if hashlib.sha256(payload).hexdigest() != DATA_SHA256:
        raise ValueError("Cached dataset checksum mismatch")
    frame = pd.read_csv(BytesIO(payload), skipinitialspace=True)
    frame = frame.apply(lambda column: column.str.strip())
    if set(frame.columns) != {*FEATURE_COLUMNS, "Target"}:
        raise ValueError("Unexpected columns in income dataset")
    if frame.isna().any().any() or not set(frame["Target"]) == {"<=50K", ">50K"}:
        raise ValueError("Invalid income dataset")
    frame.insert(0, "user_id", [f"user-{i:06d}" for i in range(len(frame))])
    frame["event_timestamp"] = SYNTHETIC_QUERY_TIME
    return frame


def split_data(frame: pd.DataFrame):
    frame = frame.sort_values("user_id").reset_index(drop=True)
    train_valid, test = train_test_split(
        frame, test_size=0.2, random_state=SEED, stratify=frame["Target"]
    )
    train, valid = train_test_split(
        train_valid, test_size=0.25, random_state=SEED, stratify=train_valid["Target"]
    )
    return train, valid, test


def prepare(settings: Settings) -> dict:
    for uri in (settings.data_root, settings.registry_uri, "s3://mlflow-artifacts"):
        ensure_bucket(uri, settings.s3_endpoint)
    frame = load_data(settings.work_dir / "income.csv")
    write_frame(
        frame, settings.data_uri(f"{SNAPSHOT}/income.parquet"), settings.s3_endpoint
    )
    for group, columns in GROUPS.items():
        features = frame[["user_id", *columns]].copy()
        features["event_timestamp"] = SYNTHETIC_FEATURE_TIME
        write_frame(
            features,
            settings.data_uri(f"{SNAPSHOT}/features/{group}.parquet"),
            settings.s3_endpoint,
        )
    _, _, test = split_data(frame)
    batch_uri = settings.data_uri(f"{SNAPSHOT}/entities.parquet")
    write_frame(test[["user_id", "event_timestamp"]], batch_uri, settings.s3_endpoint)
    return {"rows": len(frame), "batch_rows": len(test), "input_uri": batch_uri}
