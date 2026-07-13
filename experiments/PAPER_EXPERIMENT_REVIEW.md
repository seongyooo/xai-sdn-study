# 논문 관점의 실험 1·2·3 검토

> 검토일: 2026-07-13
> 대상: LLM/RAG 기반 Intent-Driven SDN 정책 생성, Static Validator,
> Mininet Digital Twin 및 XAI 설명 계층

## 1. 종합 판단

현재 실험의 구성 순서는 제안하려는 논문 프레임워크와 잘 맞는다.

```text
자연어 Network Intent
        ↓
[실험 1] LLM/RAG 기반 ONOS FlowRule 생성
        ↓
[실험 2] 스키마 및 충돌 정적 검증
        ↓
[실험 3] Mininet 기반 배포 전 실행 검증
        ↓
[XAI 계층] 생성·검증·적용/거절 근거 설명
```

따라서 시스템 구현 가능성을 보여주는 PoC 및 예비 실험으로는 가치가 높다.
특히 생성 정확도만 평가하지 않고 정적 검증과 실행 전 네트워크 검증까지
연결하려는 점은 명확한 강점이다.

다만 현재 결과만으로 다음 논문의 전체 주장을 입증하기에는 부족하다.

> 사용자의 자연어 네트워크 운영 의도를 LLM/RAG로 구조화된 SDN 정책으로
> 변환하고, 실제 적용 전에 Digital Twin에서 안전성을 검증하며, XAI 계층으로
> 정책 생성 및 적용·거절 근거를 운영자가 이해할 수 있게 제공한다.

현재 단계에서 방어 가능한 주장은 다음과 같다.

> RAG 기반 정책 생성, 정적 검증, Mininet 기반 사전 검증으로 구성된 통합
> 프로토타입을 설계하고 각 구성 요소의 실행 가능성을 예비 평가하였다.

반면 아래 주장은 추가 실험 없이 강하게 사용하기 어렵다.

- RAG가 다른 prompting 방식보다 유의하게 우수하다.
- Static Validator가 LLM 환각을 100% 탐지한다.
- Digital Twin이 잘못된 정책의 실제 적용을 안정적으로 방지한다.
- XAI 설명이 운영자의 이해도 및 의사결정 품질을 향상한다.
- 전체 프레임워크가 End-to-End 안전성을 보장한다.

## 2. 실험별 요약 평가

| 실험 | 현재 장점 | 논문상 주요 한계 |
|---|---|---|
| 실험 1 — Intent→FlowRule | 동일 데이터셋과 모델에서 Zero-shot, Few-shot, RAG 비교 | 표본 25개·단일 split, 불공정한 Few-shot baseline, RAG가 Zero-shot을 개선하지 못함 |
| 실험 2 — Static Validator | 구조 검증과 충돌 검증을 분리하고 이진 충돌 탐지 98.6% 달성 | 스키마 표본이 인위적 10개, 충돌 유형 정확도 11.1%, 설명 품질 평가 없음 |
| 실험 3 — Digital Twin | Validator→ONOS→Mininet→검증→정리 흐름 구현 | 실제 실행 결과 없음, 하드코딩된 DROP 규칙 1개, 실험 1 출력과 미연결 |

## 3. 실험 1 — LLM/RAG 기반 FlowRule 생성

### 3.1 장점

- 가장 가까운 선행 연구인 NetIntent의 IBNBench `Intent2Flow-ONOS`를 사용한다.
- 같은 생성 모델로 Zero-shot, Few-shot, RAG를 비교한다.
- exact JSON 문자열이 아니라 criteria 순서, hex 표현, 포트 타입을 정규화해
  정책 의미에 가까운 평가를 시도한다.
- 복합 VLAN/QoS 인텐트의 실패 원인을 별도로 분석했다.

### 3.2 핵심 한계

#### Few-shot baseline의 공정성

현재 Few-shot은 train set의 처음 `k`개를 고정 예시로 사용한다. 코드 주석에는
실제 NetIntent가 MMR similarity를 사용한다고 명시돼 있다. 따라서 현재 결과를
`NetIntent 방식 재현`으로 표현하면 안 되며, `fixed first-k baseline`으로 표현해야
한다. RAG가 유사도 기반 예시를 받고 baseline은 무관할 수 있는 처음 k개를 받기
때문에 RAG에 유리한 비교다.

#### RAG의 개선 효과

현재 주요 결과는 다음과 같다.

| 방식 | 정확도 |
|---|---:|
| Zero-shot | 96.0% |
| Fixed Few-shot k=3 | 92.0% |
| Fixed Few-shot k=6 | 84.0% |
| Dense RAG k=3 | 96.0% |
| Dense RAG k=6 | 96.0% |

RAG는 Zero-shot과 동률이다. 따라서 `RAG가 정확도를 향상했다`보다 `고정된
비유사 예시가 유발한 성능 저하를 피했다` 또는 `k 증가 시 성능이 유지됐다`는
제한된 결론이 적절하다. k=3과 k=6 두 점만으로 일반적인 강건성을 주장하기도
어렵다.

#### 작은 표본과 단일 실행

- 전체 50개 중 test 25개만 평가했다.
- `random_state=42`인 단일 split만 사용했다.
- 비결정적인 LLM 호출을 각 조건에서 한 번만 실행했다.
- 24/25와 23/25의 차이는 한 사례에 불과하다.
- 신뢰구간이나 paired statistical test가 없다.

#### 평가 과정의 후처리와 잠재적 과대평가

LLM 출력의 `deviceId`를 평가 전에 정규식 기반 결과로 덮어쓴다. 이는 자연어에서
대상 스위치를 식별하는 작업을 LLM 평가에서 제외한다. 이 후처리를 시스템의
명시적인 deterministic parser로 정의하거나, 후처리 전·후 성능을 분리해야 한다.

또한 평가 함수는 expected와 actual에 필드가 모두 존재할 때만 해당 필드를
비교한다. actual에 expected 필드가 누락된 경우 실패로 처리하지 않을 가능성이
있으므로 missing/extra field를 엄격히 검사하도록 수정해야 한다.

### 3.3 논문용 보강안

- 5~10개 random seed 또는 repeated generation으로 평균과 분산을 보고한다.
- Fixed random, fixed first-k, MMR, BM25, dense RAG를 공정하게 비교한다.
- `k=1, 3, 6, 10`과 retrieval corpus 구성에 대한 ablation을 수행한다.
- exact/normalized match 외에 field-level precision, recall, F1을 측정한다.
- 생성 정책의 Static Validator 통과율과 ONOS 배포 성공률을 함께 측정한다.
- `deviceId` 후처리 전·후 결과를 분리한다.
- paired bootstrap confidence interval 또는 McNemar test를 적용한다.
- 정확도뿐 아니라 latency, token usage, API cost를 보고한다.

## 4. 실험 2 — Static Validator 및 충돌 탐지

### 4.1 장점

- 문법·구조 검증과 기존 정책 충돌 검증을 분리했다.
- IBNBench `FlowConflict-ONOS` 74쌍으로 평가했다.
- 충돌 유무 이진 분류에서 73/74, Accuracy 98.6%를 얻었다.
- LLM-based와 deterministic rule-based 방식을 함께 고려했다.
- 탐지 결과에 원인, 영향, 권장 조치를 연결하는 운영자 설명 구조를 제안했다.

### 4.2 스키마 검증의 한계

`100% (10/10)`은 10개의 사전 정의된 테스트 사례에 대한 결과다. 따라서
`LLM 환각 100% 탐지`가 아니라 다음과 같이 표현해야 한다.

> 사전 정의된 10개의 정상·구조 오류 사례를 모두 올바르게 판별했다.

현재 Validator에는 다음 주장-구현 차이가 있다.

- `VALID_ETH_TYPES`와 IP CIDR 정규식이 선언돼 있지만 실제 검증에 사용되지 않는다.
- criterion은 `type`만 확인하고 type별 필수 필드를 검사하지 않는다.
- instruction도 `type`만 확인하고 OUTPUT의 port, QUEUE의 queueId 등을 검사하지 않는다.
- criterion과 instruction의 추가 필드를 허용해 잘못된 필드가 통과할 수 있다.
- 정상 사례와 오류 사례의 범위가 작아 false acceptance 및 false rejection을 알 수 없다.

### 4.3 충돌 탐지 결과의 해석

충돌 유무 이진 분류 성능과 충돌 유형 분류 성능을 분리해야 한다.

| 평가 | 결과 |
|---|---:|
| 충돌 유무 Accuracy | 98.6% (73/74) |
| 충돌 있음 클래스 F1 | 0.981 |
| 실제 충돌 27건 중 유형 exact match | 3/27 |
| 충돌 유형 정확도 | 11.1% |

실제 Shadowing은 2건이지만 LLM은 실제 충돌 27건 중 22건을 Shadowing으로
예측했다. 따라서 `충돌 탐지`는 강한 예비 결과지만, `정확한 충돌 유형 및 거절
이유 판별`은 현재 약하다.

이진 Accuracy 98.6%만 강조하고 유형 분류 결과를 숨기면 설명 가능성 주장과
충돌할 수 있으므로 반드시 두 결과를 함께 보고해야 한다.

### 4.4 설명 생성과 XAI 주장

현재 설명 실험은 5개 충돌 유형에서 첫 사례 하나씩, 총 5개 설명을 생성한
데모다. 사람 평가, 정답 설명, 자동 faithfulness 검증이 없다.

LLM이 `why`, `impact`, `remedy`를 생성하는 것만으로는 XAI 효과가 입증되지
않는다. 현 단계에서는 `LLM 기반 운영자 설명 생성`이라고 표현하는 것이 안전하다.
XAI 계층으로 주장하려면 설명이 실제 생성·검증 근거에 충실한지, 운영자의 이해와
의사결정을 개선하는지를 평가해야 한다.

### 4.5 논문용 보강안

- 실험 1의 실제 LLM 출력에서 오류 사례를 수집한다.
- 정상/비정상 mutation을 최소 100개 이상 만들고 균형 있게 평가한다.
- criterion 및 instruction type별 필수 필드와 값 범위를 검증한다.
- false acceptance rate와 false rejection rate를 별도로 측정한다.
- 충돌 유무와 충돌 유형에 대해 각각 confusion matrix 및 macro F1을 보고한다.
- LLM-based, rule-based, hybrid 방식의 정확도·결정성·비용을 비교한다.
- Validator 오류 피드백→LLM 재생성→재검증 루프의 복구 성공률을 측정한다.

## 5. 실험 3 — Mininet Digital Twin

### 5.1 장점

현재 구현은 다음의 배포 전 검증 흐름을 명확하게 구성한다.

1. Static Validator로 테스트 정책을 검사한다.
2. ONOS 준비 상태와 4개 스위치 연결을 확인한다.
3. baseline 연결성을 확인한다.
4. ONOS REST API로 고우선순위 ICMP DROP 정책을 배포한다.
5. 대상 트래픽 차단과 비대상 트래픽 연결 유지를 확인한다.
6. 테스트 정책을 삭제하고 연결 복구를 확인한다.

단순 `pingall` 성공보다 대상 정책 효과, collateral impact, cleanup 후 복구를
함께 확인한다는 점은 좋은 설계다.

### 5.2 핵심 한계

- 아직 Mininet/ONOS에서 실제 실험이 실행되지 않아 결과 파일이 없다.
- 검증 대상이 하드코딩된 ICMP DROP 규칙 하나다.
- 실험 1이 생성한 정책을 입력으로 받지 않는다.
- 실험 2의 충돌 탐지 및 적용/거절 결정과 연결되지 않는다.
- forwarding, TCP/UDP, QoS, VLAN, 경로 선택 등 다른 intent 유형을 평가하지 않는다.
- 단일 4-switch topology만 사용한다.
- 배포 성공 후 실제 ONOS flow 상태를 확인하지 않고 고정 sleep에 의존한다.
- 반복 실행, packet loss 분포, RTT, throughput, 검증 시간 측정이 없다.

### 5.3 Digital Twin 용어의 범위

현재 구현은 엄밀하게는 `Mininet 기반 pre-deployment emulation sandbox`에
가깝다. 논문에서 Digital Twin이라고 주장하려면 다음 요소를 추가하거나 범위를
명확히 정의해야 한다.

- 실제 네트워크 topology와 Mininet topology의 mapping
- 장비·링크·정책 상태 동기화
- 실제 환경 대비 emulation fidelity 평가
- 상태 변화와 장애 시나리오 반영

초기 논문에서는 `Mininet-based Network Digital Twin for pre-deployment policy
validation`으로 정의하고, 동기화 범위와 한계를 명시하는 것이 적절하다.

### 5.4 논문용 보강안

최소 다음 정책 범주를 검증해야 한다.

- allow/forward
- drop/block
- TCP/UDP 포트 기반 정책
- 경로 선택
- QoS/QUEUE
- VLAN
- 기존 정책과 충돌하는 정책
- 대상 트래픽은 처리하지만 비대상 트래픽을 손상하는 정책

각 사례에서 정책 만족 여부, 비대상 연결성, packet loss, RTT, throughput,
cleanup 후 복구, 검증 소요시간을 측정한다. 하나의 정책을 여러 번 반복하고 작은
topology와 확장 topology를 함께 평가하는 것이 좋다.

## 6. 가장 중요한 추가 실험: End-to-End Ablation

세 실험을 별도로 제시하는 것보다 동일한 자연어 intent가 전체 pipeline을
통과하도록 연결하는 실험이 논문의 핵심이다.

### 6.1 비교 구성

| 구성 | 정책 생성 | Static Validator | Digital Twin | XAI 설명 |
|---|---:|---:|---:|---:|
| A | LLM | ✗ | ✗ | ✗ |
| B | RAG+LLM | ✗ | ✗ | ✗ |
| C | RAG+LLM | ✓ | ✗ | ✗ |
| D | RAG+LLM | ✗ | ✓ | ✗ |
| E | RAG+LLM | ✓ | ✓ | ✗ |
| F | RAG+LLM | ✓ | ✓ | ✓ |

### 6.2 핵심 지표

- Intent satisfaction rate
- 잘못된 정책의 실제 적용 전 차단율
- 정상 정책 오거절률
- unsafe acceptance rate
- 정책 생성부터 적용/거절 결정까지의 latency
- Static Validator와 Digital Twin이 각각 추가로 발견한 오류 수
- 오류 피드백 후 정책 재생성 및 복구 성공률
- API/token cost

이 ablation이 있어야 `각 구성 요소가 전체 안전성에 얼마나 기여하는가`를 직접
입증할 수 있다.

## 7. XAI 평가 설계

설명은 다음 세 층의 근거를 포함해야 한다.

### 7.1 정책 생성 근거

- intent의 어떤 문구가 device, selector, treatment로 변환됐는가
- 어떤 RAG 예시가 검색됐고 similarity는 얼마인가
- 검색 예시의 어떤 필드가 생성 정책에 영향을 줬는가

### 7.2 검증 근거

- 어떤 schema 조건이 통과 또는 실패했는가
- 어떤 기존 정책과 어떤 match/action 조건에서 충돌했는가
- Digital Twin에서 어떤 packet observation이 관찰됐는가

### 7.3 적용·거절 결정 근거

- 적용 또는 거절을 결정한 직접 조건
- 예상되는 네트워크 영향
- 운영자가 취할 수 있는 수정 및 재시도 방법

### 7.4 사용자 평가

네트워크 경험자 최소 3명 이상이 다음 항목을 평가하도록 한다.

- Correctness
- Faithfulness
- Clarity
- Actionability
- Decision usefulness

가능하면 raw JSON/로그, template 설명, LLM 설명을 blind comparison하고 평가자 간
일치도(Cohen's kappa, Fleiss' kappa 또는 Krippendorff's alpha)를 보고한다.

## 8. 권장 연구 질문

- **RQ1:** Dense RAG는 Zero-shot 및 공정한 retrieval/few-shot baseline보다
  자연어 intent의 ONOS 정책 변환 정확성과 안정성을 개선하는가?
- **RQ2:** Static Validator와 hybrid conflict detector는 잘못된 정책의
  false acceptance를 얼마나 줄이는가?
- **RQ3:** Mininet Digital Twin은 정적 검증이 놓친 동적 정책 오류와 collateral
  impact를 실제 배포 전에 얼마나 탐지하는가?
- **RQ4:** 근거 기반 XAI 설명은 운영자의 정책 이해도와 적용/거절 의사결정
  정확도를 향상하는가?
- **RQ5:** 각 계층이 추가하는 안전성 개선과 latency/cost 사이의 trade-off는
  무엇인가?

## 9. 최종 결론

실험 1·2·3은 논문의 서사를 구성하는 예비 실험으로 적절하다. 각 실험은 정책
생성, 정적 안전성, 동적 사전 검증이라는 서로 다른 실패 지점을 다룬다. 특히
NetIntent에 없는 배포 전 실행 검증과 운영자 설명을 추가하려는 방향은 논문의
차별점이 될 수 있다.

그러나 현재는 구성 요소별 PoC에 가깝고 End-to-End 안전성 및 XAI 유효성을
증명하지 못했다. 최우선 작업은 새로운 독립 모듈을 추가하는 것이 아니라 다음을
완성하는 것이다.

1. 실험 1 출력이 실험 2와 실험 3을 실제로 통과하도록 연결한다.
2. 정상·오류·충돌 정책을 포함한 End-to-End ablation을 수행한다.
3. 실제 Mininet 결과와 반복 측정치를 확보한다.
4. 설명의 correctness, faithfulness, 운영자 usefulness를 평가한다.

이 네 가지를 보강하면 본 연구는 단순한 LLM 기반 FlowRule 생성 연구를 넘어,
`정책 생성→정적 검증→동적 검증→설명 가능한 적용 결정`을 통합한 안전한
Intent-Driven SDN 자동화 프레임워크로 설득력 있게 제시될 수 있다.
