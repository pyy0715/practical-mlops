# Introduction to MLOps

## Beyond the Model

머신러닝을 배운다고 하면 모델 구조와 정확도부터 떠올리기 쉽다. 하지만 예측이 잘되는 모델을 서비스로 운영하려면 데이터 수집과 검증, 배포, 모니터링까지 연결되어야 한다.

![ML 코드와 이를 둘러싼 머신러닝 시스템 구성 요소](https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEgOAfhDTYJOOIBuuGARlzE0P7qlLiY_VLJe5E8Xui2jQgQ5F_6Qj7cwZiyVpRyOqDltone7w1Et6SzQ3oO_R2mn9rdWbOVmOSznIvfYtLteTJsD0w03HWks0qYkk_l9ozk0GEUCww9-i_s/s1600/mlcode.png)

*출처: 「Hidden Technical Debt in Machine Learning Systems」(2015)*

Google의 [「Hidden Technical Debt in Machine Learning Systems」](https://proceedings.neurips.cc/paper/2015/file/86df7dcfd896fcaf2674f757a2463eba-Paper.pdf#page=5)는 성숙한 시스템에서 ML 코드가 5% 이하, 데이터를 패키지에 연결하는 코드가 95% 이상이 될 수도 있다고 설명한다. 결국 머신러닝 수명주기 전체에서 모델 자체가 차지하는 비중은 작다고 볼 수 있다.

모델을 둘러싼 작업은 프로젝트가 늘어날수록 더 큰 부담이 된다. 프로젝트마다 데이터 처리와 배포 코드를 새로 만들면, 모델이 늘어날수록 유지해야 할 연결도 늘어난다. **이 반복 작업을 공통으로 처리할 수 있는 기반이 머신러닝 플랫폼이다.**

## ML Lifecycle

먼저 정의해야 할 것은 해결하려는 문제다. 단순한 규칙으로 충분한지, 데이터 수집과 재훈련을 운영하면서까지 머신러닝을 적용할 가치가 있는지 판단해야 한다.

머신러닝이 필요하다면 문제 정의 → 데이터 준비 → 훈련 → 평가 → 배포 → 운영의 흐름을 거친다. 이 과정은 한 방향으로 끝나지 않는다. 평가 결과가 나빠 데이터를 다시 모으거나, 운영 중 발견한 문제로 목표와 평가 기준을 수정할 수도 있다.

이때 어떤 데이터와 코드, 설정으로 만든 모델인지 남아 있지 않으면 이전 결과를 재현하거나 변경의 효과를 비교하기 어렵다. 실험 단계부터 기록과 자동화를 고민해야 하는 이유다.

**머신러닝 수명주기를 설계한다는 것은 다음 실험과 변경을 감당할 수 있는 흐름을 만드는 일이다.** 개발, 스테이징, 프로덕션으로 이어지는 과정에서도 같은 모델과 처리 과정을 추적할 수 있어야 한다.

## Shared Platform

이 반복을 여러 팀이 겪으면 조직 차원의 문제가 된다. Uber의 [2017년 Michelangelo 소개 글](https://www.uber.com/blog/michelangelo-machine-learning-platform/)에서는 프로젝트마다 서빙 컨테이너를 따로 만들고, 실험 결과를 저장하고 비교하는 표준 경로도 부족했던 상황을 설명한다. Michelangelo는 데이터 관리부터 훈련, 평가, 배포, 예측, 모니터링까지 공통 흐름을 제공했다.

![Michelangelo의 온라인과 오프라인 데이터 준비 파이프라인](https://tb-static.uber.com/prod/udam-assets/c16cb7bc-7dd3-593b-b7fd-b59af38c73a0.jpg)

*출처: Uber Engineering, 「Meet Michelangelo: Uber’s Machine Learning Platform」(2017)*

Uber는 피처를 팀 간에 공유하고, 훈련과 예측에서 데이터 처리의 일관성을 유지하는 데도 집중했다. 모델마다 시스템을 따로 구축하던 부담을 공통 기반으로 옮긴 것이다.

플랫폼의 가치는 **다음 모델과 다음 팀이 운영에 도달하는 데 드는 시간과 중복 작업을 줄이는 데 있다.**

## Tool Selection

그렇다면 공통 기반을 어디까지 만들어야 할까? BentoML, Databricks처럼 선택지는 많지만 제공하는 범위가 다르다. 먼저 우리 팀에서 반복되는 작업과 막히는 지점을 알아야 도구도 비교할 수 있다.

변성윤 님의 [「MLOps 춘추 전국 시대 정리」](https://speakerdeck.com/mlopskr/mlops-cuncu-jeongug-sidae-jeongri-byeonseongyun)(2021)에서도 점진적인 접근을 설명한다. 실시간 응답이 필요하지 않으면 배치 예측을 DB에 저장하는 방식으로 시작할 수 있다고 설명한다. 피처 스토어 역시 집계한 피처를 DB 테이블에 저장하는 출발점을 소개하며, 훈련과 운영에서 일관되게 사용하는 것을 강조한다.

**필요한 역할을 먼저 정하고, 반복되는 부담에 맞춰 도구를 도입해야 한다.** 책에서 사용하는 도구도 해결하려는 문제와 연결하면 역할이 명확해진다.

| 역할 | 도구 | 해결하려는 문제 |
| --- | --- | --- |
| 파이프라인 오케스트레이션 | Kubeflow Pipelines | 여러 단계를 연결하고 반복 실행하기 |
| 피처 관리 | Feast | 훈련과 서빙에 필요한 피처를 일관되게 제공하기 |
| 실험 추적과 모델 관리 | MLflow | 실험 조건과 결과를 비교하고 모델 버전을 관리하기 |

특정 벤더의 플랫폼을 쓰더라도 각 역할과 연결 구조를 이해해야 한다. 그래야 제공되는 기능으로 충분한지, 어디를 보완해야 하는지 판단할 수 있다.

직접 구축해 보는 경험의 의미도 여기에 있다. 컴포넌트를 연결하면서 비용과 복잡성이 생기는 지점을 배울 수 있다. 이 책에서는 설치 방법과 함께 **왜 이 컴포넌트가 필요하고, 우리 상황에서는 생략하거나 대체할 수 있는지**를 중심으로 생각해 보려 한다.
