import json
import re
from importlib.metadata import version as package_version

import mlflow
import mlflow.sklearn
import pandas as pd
from mlflow import MlflowClient
from mlflow.models import infer_signature
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sklearn.tree import DecisionTreeClassifier

from income_lab.config import Settings
from income_lab.data import (
    DATA_SHA256,
    FEATURE_COLUMNS,
    SEED,
    SNAPSHOT,
    UPSTREAM_COMMIT,
    split_data,
)
from income_lab.features import FEATURE_SERVICE, get_store, historical
from income_lab.storage import read_frame

MODEL_NAME = "income-classifier"
TRUSTED_TYPES = ["sklearn.tree._tree.Tree"]


def make_model(estimator: str, seed: int) -> Pipeline:
    classifiers = {
        "tree": DecisionTreeClassifier(max_depth=10, random_state=seed),
        "forest": RandomForestClassifier(
            n_estimators=100, max_depth=12, random_state=seed, n_jobs=2
        ),
    }
    return Pipeline(
        [
            ("encoder", OneHotEncoder(handle_unknown="ignore")),
            ("classifier", classifiers[estimator]),
        ]
    )


def evaluate(model: Pipeline, frame: pd.DataFrame) -> dict[str, float]:
    inputs = frame[FEATURE_COLUMNS]
    labels = frame["Target"].eq(">50K").astype(int)
    positive = list(model.classes_).index(1)
    return {
        "accuracy": float(accuracy_score(labels, model.predict(inputs))),
        "roc_auc": float(
            roc_auc_score(labels, model.predict_proba(inputs)[:, positive])
        ),
    }


def train(settings: Settings) -> dict:
    mlflow.set_tracking_uri(settings.tracking_uri)
    mlflow.set_experiment("income-classifier")
    source = settings.data_uri(f"{SNAPSHOT}/income.parquet")
    raw = read_frame(source, settings.s3_endpoint)
    joined = historical(get_store(settings), raw[["user_id", "event_timestamp"]])
    frame = (
        joined.merge(
            raw[["user_id", "event_timestamp", "Target"]],
            on=["user_id", "event_timestamp"],
            validate="one_to_one",
        )
        .sort_values("user_id")
        .reset_index(drop=True)
    )
    training, validation, testing = split_data(frame)
    lineage = {
        "dataset_sha256": DATA_SHA256,
        "upstream_commit": UPSTREAM_COMMIT,
        "feature_service": FEATURE_SERVICE,
        "synthetic_event_times": True,
    }
    results = []
    requirements = [
        f"{name}=={package_version(name)}"
        for name in ("mlflow", "scikit-learn", "pandas", "numpy", "scipy", "skops")
    ]
    for estimator in ("tree", "forest"):
        model = make_model(estimator, SEED)
        with mlflow.start_run(run_name=estimator) as run:
            model.fit(
                training[FEATURE_COLUMNS], training["Target"].eq(">50K").astype(int)
            )
            metrics = evaluate(model, validation)
            mlflow.log_params(
                {
                    "estimator": estimator,
                    "split_seed": SEED,
                    "train_ratio": 0.6,
                    "validation_ratio": 0.2,
                    **model["classifier"].get_params(),
                }
            )
            mlflow.log_metrics(
                {f"validation_{key}": value for key, value in metrics.items()}
            )
            mlflow.set_tags(
                {"dataset_sha256": DATA_SHA256, "feature_service": FEATURE_SERVICE}
            )
            for name, split in (("training", training), ("validation", validation)):
                mlflow.log_input(
                    mlflow.data.from_pandas(split, source=source, targets="Target"),
                    context=name,
                )
            info = mlflow.sklearn.log_model(
                model,
                name="model",
                signature=infer_signature(
                    training[FEATURE_COLUMNS], model.predict(training[FEATURE_COLUMNS])
                ),
                input_example=training[FEATURE_COLUMNS].head(3),
                serialization_format="skops",
                skops_trusted_types=TRUSTED_TYPES,
                pip_requirements=requirements,
            )
            mlflow.log_dict(lineage, "provenance.json")
            results.append(
                {
                    "estimator": estimator,
                    "validation": metrics,
                    "run_id": run.info.run_id,
                    "logged_uri": info.model_uri,
                }
            )
    best = max(results, key=lambda result: result["validation"]["roc_auc"])
    restored = mlflow.sklearn.load_model(best["logged_uri"])
    test_metrics = evaluate(restored, testing)
    version = mlflow.register_model(best["logged_uri"], MODEL_NAME)
    model_uri = f"models:/{MODEL_NAME}/{version.version}"
    MlflowClient().set_registered_model_alias(MODEL_NAME, "candidate", version.version)
    report = {
        **lineage,
        "model_uri": model_uri,
        "run_id": best["run_id"],
        "selected_estimator": best["estimator"],
        "test": test_metrics,
        "split_rows": {
            "training": len(training),
            "validation": len(validation),
            "testing": len(testing),
        },
        "candidates": results,
    }
    with mlflow.start_run(run_id=best["run_id"]):
        mlflow.log_metrics(
            {f"test_{key}": value for key, value in test_metrics.items()}
        )
        mlflow.log_dict(report, "selection.json")
    return report


def predict(settings: Settings, features: pd.DataFrame, model_uri: str) -> pd.DataFrame:
    if not re.fullmatch(r"models:/income-classifier/[1-9][0-9]*", model_uri):
        raise ValueError("Use an immutable models:/income-classifier/<version> URI")
    if features[FEATURE_COLUMNS].isna().any().any():
        raise ValueError("Inference features contain missing values")
    mlflow.set_tracking_uri(settings.tracking_uri)
    model = mlflow.sklearn.load_model(model_uri)
    inputs = features[FEATURE_COLUMNS]
    positive = list(model.classes_).index(1)
    result = features[["user_id", "event_timestamp"]].copy()
    result["income_probability"] = model.predict_proba(inputs)[:, positive]
    result["predicted_income"] = model.predict(inputs)
    result["model_uri"] = model_uri
    return result


if __name__ == "__main__":
    print(json.dumps(train(Settings.from_env()), indent=2))
