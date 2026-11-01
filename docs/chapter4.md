# Designing Reliable ML Systems

## Reliable and Reproducible Experiments

머신러닝 실험에서는 결과를 신뢰할 수 있어야 하고, 같은 조건으로 다시 실행해 그 결과를 확인할 수 있어야 한다. 정확도가 높게 나와도 어떤 데이터와 설정을 사용했는지 모르면 모델을 서비스에 적용하기 어렵다. 실험을 다시 실행했을 때 결과가 달라진다면 그 이유도 설명할 수 있어야 한다.

실험을 재현하려면 코드와 함께 학습 데이터, 전처리 방식, 모델 설정, 라이브러리 버전을 남겨야 한다. 모두 결과에 영향을 주는 요소다. 여러 모델의 성능을 비교할 때도 같은 데이터와 평가 기준을 사용해야 개선 여부를 판단할 수 있다.

실험이 늘어나면 파일과 노트북만으로 이 정보를 관리하기 어려워진다. MLflow는 실험 조건과 결과를 기록하고 모델 버전을 관리한다. Feast는 피처 정의와 조회 방법을 공유해 학습과 추론에서 일관된 데이터를 사용하도록 돕는다.

소득 분류 실습에서는 직업, 학력, 혼인 상태 등의 피처로 소득이 `50K 이하`인지 `50K 초과`인지 예측한다. 여러 모델을 같은 조건에서 비교하고, 선택한 모델을 저장한 뒤 다시 불러와 예측하는 과정을 살펴본다.

## Tracking Experiments with MLflow

MLflow에서는 관련 실험을 Experiment로 묶고, 한 번의 실행을 Run으로 기록한다. 모델 설정을 바꿀 때마다 Run을 남기면 어떤 조건에서 성능이 달라졌는지 비교할 수 있다.

| 구분 | 기록할 내용 |
| --- | --- |
| Parameters | 모델 종류, 트리 깊이, 난수 시드, 데이터 분리 비율 |
| Metrics | 정확도, ROC AUC, 학습 시간 |
| Datasets | 데이터 출처와 버전, 학습용과 평가용 데이터의 분리 정보 |
| Artifacts | 분석 그래프, 학습된 모델, 전처리 객체, 입력 예시 |
| Tags | 코드 커밋, 실행 환경, 피처 정의 버전 |

## MLflow Architecture

MLflow 서버는 실험 메타데이터와 모델 파일을 별도의 저장소에 기록한다. [공식 아키텍처 문서](https://mlflow.org/docs/latest/self-hosting/architecture/overview/)에서 저장소에 직접 접근하는 구성과 Tracking Server를 거치는 구성을 비교할 수 있다.

![MLflow의 로컬 실행과 원격 Tracking Server 구성](https://mlflow.org/docs/latest/assets/images/tracking-setup-overview-3d8cfd511355d9379328d69573763331.png)

| 구성 요소 | 역할 | 실습 구성 |
| --- | --- | --- |
| Client SDK | 실험 기록과 모델 조회 요청 | Python MLflow 클라이언트 |
| Tracking Server | 실험 기록 API와 UI 제공 | Kubernetes Deployment와 Service |
| Backend Store | 실행 정보, 파라미터, 지표, 모델 버전 저장 | PostgreSQL |
| Artifact Store | 모델 파일, 그래프, 데이터 파일 저장 | S3 호환 객체 저장소 |

Kubernetes에 공용 MLflow 서버를 설치해 학습 코드와 추론 파이프라인에서 함께 사용한다. PostgreSQL과 객체 저장소에는 영속 스토리지를 연결해 Pod가 다시 생성되어도 실험 기록과 모델이 남도록 한다.

아티팩트 전송도 MLflow 서버를 거치도록 구성한다. 클라이언트는 MLflow에 모델 저장과 조회를 요청하고, 서버가 객체 저장소에 접속해 파일을 전송한다. 구체적인 설정은 [Tracking Server의 아티팩트 접근 방식](https://mlflow.org/docs/latest/self-hosting/architecture/tracking-server/#remote-artifacts-store)을 참고한다.

## Training and Model Management

데이터를 학습용, 검증용, 테스트용으로 나누고 모든 모델에 같은 분리 기준을 적용한다. 전처리와 분류기를 하나의 Pipeline으로 묶어 함께 저장한다. scikit-learn의 [데이터 누수 방지 가이드](https://scikit-learn.org/stable/common_pitfalls.html#data-leakage)에서 설명하듯, 전처리 규칙은 학습 데이터로만 정하고 검증용과 테스트용 데이터에는 이미 정한 규칙을 적용한다.

한 번의 학습과 평가를 Run으로 묶어 설정, 지표, 모델을 함께 기록한다. 아래 코드에서 `model`은 전처리를 포함한 모델을, `params`와 `metrics`는 실험 설정과 평가 결과를 나타낸다.

```python
with mlflow.start_run():
    model.fit(X_train, y_train)
    mlflow.log_params(params)
    mlflow.log_metrics(metrics)
    info = mlflow.sklearn.log_model(
        model, name="model", skops_trusted_types=["sklearn.tree._tree.Tree"]
    )
```

`skops_trusted_types`에는 직접 학습한 트리의 내부 자료형을 지정했다. 저장한 모델 중 검증 성능이 좋은 모델을 [Model Registry](https://mlflow.org/docs/latest/ml/model-registry/workflow/)에 등록하고, 버전을 지정해 다시 불러온다.

```python
version = mlflow.register_model(info.model_uri, "income-classifier")
model_uri = f"models:/income-classifier/{version.version}"
restored = mlflow.sklearn.load_model(model_uri)
predictions = restored.predict(X_test)
```

검증 데이터로 모델을 선택한 뒤 테스트 데이터로 최종 성능을 평가한다. 추론 결과에는 사용한 모델 버전도 남겨 결과를 만든 모델을 추적할 수 있도록 한다.

## Managing Features with Feast

학습과 추론에서 피처를 만드는 방식이 다르면 같은 모델이라도 예측 결과가 달라질 수 있다. 데이터가 여러 테이블에 흩어져 있으면 필요한 피처를 조합하는 코드도 반복해서 작성하게 된다. Feast를 사용하면 피처 정의와 조회 방법을 공유해 이런 차이와 중복 작업을 줄일 수 있다.

| 개념 | 역할 |
| --- | --- |
| Entity | 피처를 조회할 대상과 조인 키 |
| Data Source | 데이터의 위치와 시간 열 |
| Feature View | 피처 묶음의 스키마, 출처, TTL |
| Feature Service | 모델에서 사용하는 피처의 조합 |
| Registry | 피처 정의와 저장소 연결 정보 |
| Materialization | 오프라인 피처를 온라인 스토어에 적재하는 작업 |

소득 예측에 사용할 피처를 인구통계, 관계, 직업의 세 범주로 나누고, 모델에 필요한 피처를 `income_v1`이라는 Feature Service로 묶는다. 피처 데이터에는 조회 키인 `user_id`와 피처의 기록 시각을 나타내는 `event_timestamp`가 있어야 한다.

## Point-in-Time Joins

과거 데이터를 학습에 사용할 때는 예측 시점 이후의 정보가 섞이지 않도록 해야 한다. 예를 들어 5월 22일의 예측을 재현하는 데 12월에 갱신된 직업 정보를 사용하면, 당시에는 알 수 없었던 정보까지 학습에 포함된다.

Feast의 [Point-in-time join](https://docs.feast.dev/getting-started/concepts/point-in-time-joins)은 엔티티별 기준 시각 이전의 값 중 TTL 범위에 있는 최신 값을 조회한다. 사용자 ID와 기준 시각이 담긴 `entity_df`를 전달하면 피처를 조합한 데이터를 얻을 수 있다.

```python
features = store.get_historical_features(
    entity_df=entity_df,
    features=store.get_feature_service("income_v1"),
).to_df()
```

온라인으로 피처를 조회하려면 먼저 오프라인 피처를 온라인 스토어에 적재한다. `start`와 `end`는 적재 구간의 시작 시각과 종료 시각이다.

```python
store.materialize(start, end)
online_features = store.get_online_features(
    features=store.get_feature_service("income_v1"),
    entity_rows=[{"user_id": "user-001"}],
).to_dict()
```

[Feast Quickstart](https://docs.feast.dev/getting-started/quickstart)에서도 과거 시점 조회와 온라인 조회를 구분한다. 학습과 배치 추론에는 오프라인 스토어를, 최신 피처를 빠르게 조회해야 하는 서비스에는 온라인 스토어를 사용할 수 있다.
