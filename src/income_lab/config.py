import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


@dataclass(frozen=True)
class Settings:
    data_root: str = "s3://income-data"
    registry_uri: str = "s3://feature-registry/income/registry.pb"
    s3_endpoint: str = "http://seaweedfs.kubeflow.svc.cluster.local:8333"
    redis_host: str = "income-redis.kubeflow.svc.cluster.local:6379"
    tracking_uri: str = "http://mlflow-service.kubeflow.svc.cluster.local:5000"
    work_dir: Path = Path(".local/income")

    @classmethod
    def from_env(cls):
        settings = cls(
            data_root=os.getenv("INCOME_DATA_ROOT", cls.data_root).rstrip("/"),
            registry_uri=os.getenv("FEAST_REGISTRY_URI", cls.registry_uri),
            s3_endpoint=os.getenv("AWS_ENDPOINT_URL", cls.s3_endpoint),
            redis_host=os.getenv("REDIS_HOST", cls.redis_host),
            tracking_uri=os.getenv("MLFLOW_TRACKING_URI", cls.tracking_uri),
            work_dir=Path(os.getenv("INCOME_WORK_DIR", str(cls.work_dir))),
        )
        if urlparse(settings.tracking_uri).scheme not in {"http", "https"}:
            raise ValueError("MLFLOW_TRACKING_URI must point to the shared HTTP server")
        os.environ.setdefault("FEAST_S3_ENDPOINT_URL", settings.s3_endpoint)
        os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
        os.environ.setdefault("FEAST_USAGE", "False")
        return settings

    def data_uri(self, name: str) -> str:
        return f"{self.data_root}/{name}"
