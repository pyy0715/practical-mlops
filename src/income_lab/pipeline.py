import argparse
import os
from pathlib import Path

from kfp import compiler, dsl, kubernetes

IMAGE = os.getenv("INCOME_PIPELINE_IMAGE", "income-lab:dev")


@dsl.component(base_image=IMAGE, install_kfp_package=False)
def read_data(input_uri: str, output: dsl.Output[dsl.Dataset]):
    import pandas as pd

    from income_lab.config import Settings
    from income_lab.storage import read_frame, write_frame

    settings = Settings.from_env()
    entities = read_frame(input_uri, settings.s3_endpoint)[
        ["user_id", "event_timestamp"]
    ]
    entities["event_timestamp"] = pd.to_datetime(entities["event_timestamp"], utc=True)
    write_frame(entities, output.path, settings.s3_endpoint)


@dsl.component(base_image=IMAGE, install_kfp_package=False)
def retrieve_features(
    entities: dsl.Input[dsl.Dataset], output: dsl.Output[dsl.Dataset]
):
    from income_lab.config import Settings
    from income_lab.features import get_store, historical
    from income_lab.storage import read_frame, write_frame

    settings = Settings.from_env()
    inputs = read_frame(entities.path, settings.s3_endpoint)
    result = historical(get_store(settings), inputs)
    write_frame(result, output.path, settings.s3_endpoint)


@dsl.component(base_image=IMAGE, install_kfp_package=False)
def run_inference(
    features: dsl.Input[dsl.Dataset], model_uri: str, output: dsl.Output[dsl.Dataset]
):
    from income_lab.config import Settings
    from income_lab.model import predict
    from income_lab.storage import read_frame, write_frame

    settings = Settings.from_env()
    frame = read_frame(features.path, settings.s3_endpoint)
    write_frame(predict(settings, frame, model_uri), output.path, settings.s3_endpoint)


@dsl.component(base_image=IMAGE, install_kfp_package=False)
def write_data(predictions: dsl.Input[dsl.Dataset], output_uri: str):
    from income_lab.config import Settings
    from income_lab.storage import read_frame, write_frame

    settings = Settings.from_env()
    frame = read_frame(predictions.path, settings.s3_endpoint)
    write_frame(frame, output_uri, settings.s3_endpoint)


@dsl.pipeline(name="income-classifier")
def income_pipeline(input_uri: str, output_uri: str, model_uri: str):
    data = read_data(input_uri=input_uri)
    features = retrieve_features(entities=data.outputs["output"])
    predictions = run_inference(
        features=features.outputs["output"], model_uri=model_uri
    )
    write = write_data(predictions=predictions.outputs["output"], output_uri=output_uri)
    for task in (data, features, predictions, write):
        task.set_caching_options(False)
        kubernetes.use_secret_as_env(
            task,
            secret_name="income-lab",
            secret_key_to_env={"REDIS_PASSWORD": "REDIS_PASSWORD"},
        )
        kubernetes.use_secret_as_env(
            task,
            secret_name="mlpipeline-minio-artifact",
            secret_key_to_env={
                "accesskey": "AWS_ACCESS_KEY_ID",
                "secretkey": "AWS_SECRET_ACCESS_KEY",
            },
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", type=Path, default=Path(".local/income/pipeline.yaml")
    )
    args = parser.parse_args()
    if not os.getenv("INCOME_PIPELINE_IMAGE"):
        parser.error("Set INCOME_PIPELINE_IMAGE to the built image reference")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    compiler.Compiler().compile(income_pipeline, str(args.output))
    print(args.output)


if __name__ == "__main__":
    main()
