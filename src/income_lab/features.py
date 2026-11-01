import os
from datetime import timedelta

import pandas as pd
from feast import (
    Entity,
    FeatureService,
    FeatureStore,
    FeatureView,
    Field,
    FileSource,
    ValueType,
)
from feast.repo_config import RepoConfig
from feast.types import String

from income_lab.config import Settings
from income_lab.data import (
    GROUPS,
    SNAPSHOT,
    SYNTHETIC_FEATURE_TIME,
    SYNTHETIC_QUERY_TIME,
)

FEATURE_SERVICE = "income_v1"


def get_store(settings: Settings) -> FeatureStore:
    password = os.environ.get("REDIS_PASSWORD", "")
    if not password:
        raise ValueError("REDIS_PASSWORD must be provided")
    return FeatureStore(
        config=RepoConfig(
            project="income_lab",
            provider="local",
            registry={"path": settings.registry_uri, "cache_ttl_seconds": 0},
            offline_store={"type": "file"},
            online_store={
                "type": "redis",
                "connection_string": f"{settings.redis_host},password={password}",
            },
            entity_key_serialization_version=3,
        )
    )


def definitions(settings: Settings):
    user = Entity(name="user", join_keys=["user_id"], value_type=ValueType.STRING)
    views = [
        FeatureView(
            name=group,
            entities=[user],
            ttl=timedelta(days=365),
            schema=[Field(name=column, dtype=String) for column in columns],
            source=FileSource(
                name=f"{group}_source",
                path=settings.data_uri(f"{SNAPSHOT}/features/{group}.parquet"),
                timestamp_field="event_timestamp",
                s3_endpoint_override=settings.s3_endpoint or None,
            ),
        )
        for group, columns in GROUPS.items()
    ]
    service = FeatureService(name=FEATURE_SERVICE, features=views)
    return [user, *views, service]


def apply(settings: Settings) -> dict:
    store = get_store(settings)
    store.apply(definitions(settings))
    store.materialize(
        SYNTHETIC_FEATURE_TIME.to_pydatetime(), SYNTHETIC_QUERY_TIME.to_pydatetime()
    )
    return {"feature_service": FEATURE_SERVICE, "registry": settings.registry_uri}


def historical(store: FeatureStore, entities: pd.DataFrame) -> pd.DataFrame:
    keys = ["user_id", "event_timestamp"]
    if entities[keys].isna().any().any() or entities.duplicated(keys).any():
        raise ValueError("Entity keys must be non-null and unique")
    result = store.get_historical_features(
        entity_df=entities[keys],
        features=store.get_feature_service(FEATURE_SERVICE),
    ).to_df()
    if len(result) != len(entities) or result.isna().any().any():
        raise ValueError("Historical retrieval returned missing or unexpected rows")
    return result


def online(settings: Settings, user_id: str) -> dict:
    store = get_store(settings)
    values = store.get_online_features(
        features=store.get_feature_service(FEATURE_SERVICE),
        entity_rows=[{"user_id": user_id}],
    ).to_dict()
    if any(value[0] is None for value in values.values()):
        raise ValueError("Online lookup returned missing features")
    return values
