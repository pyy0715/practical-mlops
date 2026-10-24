# Building on Kubernetes

## Infrastructure

EKS 위에 FastAPI 애플리케이션과 GitLab Runner, Argo CD, Prometheus·Grafana를 구성한다. Kubernetes control plane은 AWS에 맡기고 애플리케이션의 배포와 운영 흐름에 집중한다.

GitLab은 별도 EC2에 직접 설치한다. 소스와 이미지 레지스트리는 실습 클러스터를 다시 만들더라도 유지하고, 실습하지 않을 때는 EC2를 중지한다. EKS는 Terraform의 `apply`와 `destroy`로 생성·삭제한다.

[HashiCorp의 구성 가이드](https://developer.hashicorp.com/terraform/tutorials/kubernetes/kubernetes-provider)에 따라 EKS와 Argo CD 부트스트랩은 별도 state로 관리한다. 종료할 때는 Argo CD가 배포한 리소스를 먼저 정리하고, 부트스트랩과 EKS를 역순으로 삭제한다. GitLab 데이터는 이 삭제 범위에서 분리한다.

## Reproducible Environment

Python과 uv 버전, 개발·검증 명령은 mise로 관리한다. Python 의존성은 `pyproject.toml`에 선언하고 `uv.lock`으로 고정한다. 로컬과 CI, Docker 빌드에서 같은 lockfile을 사용한다.

FastAPI 애플리케이션은 컨테이너 이미지로 배포하고, 커밋과 이미지 digest를 연결한다. 로컬 Mac은 ARM64, EKS 노드는 x86_64이므로 배포 이미지는 `linux/amd64`로 빌드한다.

**코드뿐 아니라 도구와 의존성, 이미지까지 연결해야 같은 실행 환경을 재현할 수 있다.**

## GitOps Bridge

Terraform으로 AWS 인프라와 Argo CD를 구성하고, 클러스터 이름과 리전을 Root Application의 Helm values로 전달한다. [GitOps Bridge](https://github.com/gitops-bridge-dev/gitops-bridge)는 이렇게 인프라 생성 결과를 GitOps에 연결하는 패턴이다.

Root Application은 [App of Apps](https://argo-cd.readthedocs.io/en/stable/operator-manual/cluster-bootstrapping/) 패턴으로 모니터링·Runner·FastAPI의 하위 Application을 관리한다. 현재는 단일 클러스터이므로 별도의 ApplicationSet 없이 Root Application으로 연결한다.

```text
src/hello_joker/          FastAPI 소스
infra/terraform/eks/     VPC·EKS·노드
infra/terraform/bootstrap/  Argo CD 설치와 최초 연결
apps/argocd/bootstrap/   Root Application
apps/argocd/root/        하위 Application 선언
apps/addons/             Argo CD·모니터링·Runner values
apps/workloads/hello-joker/  애플리케이션 Helm chart
```

Terraform은 AWS 리소스와 최초 연결을, Argo CD는 클러스터 안의 애드온과 애플리케이션을 관리한다. 모니터링·Runner·FastAPI는 실습의 고정 구성으로 선언하고, 활성화 여부를 Terraform 변수로 다시 관리하지 않는다. 사용하지 않는 SSO·알림 기능은 비활성화한다.

**확장성은 모든 선택지를 미리 만드는 것보다, 각 구성의 책임과 변경 위치를 명확하게 나누는 데서 확보한다.**

## Runner Capacity

Runner는 Kubernetes executor로 CI 작업마다 Pod를 실행한다. 우선 On-Demand 노드 한 대로 시작하고, CI를 연결할 때 재실행 가능한 job Pod를 Spot에 배치하는 구성을 검토한다. Runner manager와 Argo CD·모니터링은 On-Demand에 유지한다.

[GitLab의 node selector 설정](https://docs.gitlab.com/runner/executors/kubernetes/#specify-the-node-to-execute-builds)으로 job Pod의 실행 위치를 구분할 수 있다. Spot node group에는 [AWS 권고](https://docs.aws.amazon.com/eks/latest/APIReference/API_CreateNodegroup.html)에 따라 비슷한 사양의 인스턴스 종류를 여러 개 지정한다. 중단된 작업은 CI에서 재시도할 수 있도록 구성한다.

자동 확장이 필요해질 때 autoscaler를 추가한다. 노드 그룹의 최대 크기를 늘리는 것만으로 대기 중인 CI 작업에 맞춰 노드가 생성되지는 않는다.

## Delivery and Observability

GitLab CI에서 코드를 검증하고 이미지를 빌드해 레지스트리에 올린다. 배포 설정의 이미지 참조를 갱신하면 Argo CD가 Git 변경을 감지해 Kubernetes에 반영한다. GitLab 주소와 Runner 설정은 `apps/addons/gitlab-runner/values.yaml`에서 관리하고, 인증 토큰은 Secret으로 분리한다.

Prometheus는 애플리케이션과 클러스터 지표를 수집하고, Grafana는 이를 대시보드로 보여준다. 배포 성공 여부와 함께 요청 오류율·지연시간·자원 사용량을 확인하도록 구성한다.
