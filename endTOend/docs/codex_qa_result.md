# Codex QA Result and End-to-End Plan

> 작성일: 2026-07-16  
> 대상: `endTOend/` 파이프라인  
> 원칙: 코드 수정 없이 현재 프로젝트 분석, QA 결과, 향후 계획만 정리

---

## 1. 프로젝트 현재 상태 요약

현재 `endTOend/`는 자연어 네트워크 인텐트를 받아 다음 6단계로 처리하는 XAI 기반 SDN 자동화 파이프라인이다.

```text
Natural Language Intent
  -> Stage 1: LLM/RAG Intent Parsing
  -> Stage 2: Deterministic FlowRule Compiler
  -> Stage 3: Static Validator
  -> Stage 4: Digital Twin Verification
  -> Stage 5: XAI Explanation
  -> Stage 6: ONOS Deployment
```

핵심 설계는 적절하다. 특히 LLM이 ONOS FlowRule을 직접 생성하지 않고, 먼저 `IntentIR`이라는 중간 표현을 만들고, 이후 FlowRule 생성은 결정론적 컴파일러가 담당하는 구조는 연구와 운영 안정성 측면에서 강점이다.

다만 현재 구현은 "동작하는 연구 프로토타입"에 가깝고, 논문/데모/운영 검증을 위해서는 QA 안정화가 필요하다.

---

## 2. QA 범위

이번 QA에서는 코드를 수정하지 않고 다음만 수행했다.

- `README.md`, `RESULTS.md`, `endTOend/IMPLEMENTATION.md`, `endTOend/plan.md`, `endTOend/ROADMAP.md` 검토
- `pipeline.py`, `app.py`, `config.py` 검토
- Stage 1~6 핵심 모듈 정적 리뷰
- 외부 LLM, ONOS, Mininet, Streamlit 서버를 실행하지 않는 범위에서 짧은 Python 드라이런 수행
- `IntentIR -> compile_flowrule -> validate -> XAIExplainer` 결정론적 경로 확인

이번 QA에서 실행하지 않은 항목:

- 외부 LLM/Ollama/Gemini 호출
- RAG 임베딩 인덱스 구축
- ONOS REST API 호출
- Mininet Digital Twin 실행
- Streamlit UI 실행
- 코드 수정

---

## 3. 확인된 강점

### 3.1 LLM 역할 제한

LLM을 FlowRule 생성 전체에 사용하지 않고 `IntentIR` 추출에 제한한 점이 좋다. 이 구조는 LLM hallucination이 바로 컨트롤러 배포 형식으로 이어지는 위험을 줄인다.

### 3.2 결정론적 컴파일러

`stage2_flowrule/compiler.py`는 `IntentIR`을 ONOS FlowRule JSON으로 변환한다. 같은 IR이 들어오면 같은 FlowRule이 생성되므로 재현성이 있다.

### 3.3 정적 검증과 Digital Twin 분리

Stage 3는 구조/충돌 검증, Stage 4는 실제 네트워크 동작 검증으로 역할이 분리되어 있다. 논문 구조상 "static safety + runtime validation" 메시지를 만들기 좋다.

### 3.4 Evidence-grounded XAI 구조

Stage 5는 각 단계 결과를 evidence로 모으는 구조를 갖고 있다. 이후 confidence, rollback impact, counterfactual explanation을 추가하기 좋은 기반이다.

---

## 4. QA에서 확인된 주요 이슈

### Issue 1. 실제 CLI/UI에서 충돌 탐지가 사실상 비활성화됨

위치:

- `endTOend/pipeline.py`
- `endTOend/app.py`

현재 두 진입점 모두 정적 검증을 다음처럼 호출한다.

```python
static_result = static_validate(flowrule, existing_flows=None)
```

이 경우 schema validation은 동작하지만, 기존 ONOS FlowRule과의 conflict detection은 수행되지 않는다.

영향:

- "Static Validator가 충돌을 탐지한다"는 문서/논문 주장과 실제 CLI/UI 동작 사이에 차이가 생긴다.
- 운영자가 기존 룰과 충돌하는 새 룰을 넣어도 Stage 3에서 통과할 수 있다.

권장 방향:

- `--use-existing-flows` 또는 기본 ONOS 조회 옵션 추가
- `OnosClient.flows()` 결과를 `existing_flows`에 주입
- ONOS 연결 실패 시 `warning` 또는 `static_conflict_check=skipped`를 명시

---

### Issue 2. `s2`, `s4` 축약 스위치명 파싱 불일치

위치:

- `endTOend/stage2_flowrule/compiler.py`

문서/주석은 `"s4" -> "of:0000000000000004"`를 지원한다고 설명하지만, 실제 정규식은 단독 숫자만 찾는다.

현재 로직:

```python
num_match = re.search(r"\b(\d+)\b", hint)
```

QA 드라이런 결과:

```text
device_hint='s2' -> CompileError
```

영향:

- LLM이 `device_hint`를 `"s2"`처럼 반환하면 Stage 2에서 실패한다.
- 문서상 지원 범위와 실제 구현이 다르다.

권장 방향:

- `s(\d+)`, `sw(\d+)`, `switch(\d+)` 형태를 명시적으로 지원
- device hint normalization 테스트 추가

---

### Issue 3. XAI FlowRule 요약에서 `NOACTION` 차단 룰을 잘못 표시

위치:

- `endTOend/stage5_xai/explainer.py`

Stage 2는 block action을 다음처럼 생성한다.

```json
{"type": "NOACTION"}
```

하지만 XAI 요약은 `treatment is None`일 때만 `DROP`으로 보고, treatment가 있으면 `FORWARD/QoS`로 표시한다.

영향:

- 실제 차단 룰인데 XAI 설명에서는 `FORWARD/QoS`로 표시될 수 있다.
- 운영자 신뢰도와 논문 XAI 주장에 직접적인 악영향이 있다.

권장 방향:

- instruction 목록에 `NOACTION`만 있으면 `DROP`으로 표시
- `OUTPUT`이 있으면 `FORWARD`
- `QUEUE`가 있으면 `QoS`
- 혼합 instruction은 상세 표시

---

### Issue 4. Digital Twin이 skipped여도 최종 APPROVE 가능

위치:

- `endTOend/stage5_xai/explainer.py`

현재 판정:

```python
twin_passed = twin_result.status in ("passed", "skipped")
decision = "APPROVE" if static_result.passed and twin_passed else "REJECT"
```

영향:

- Windows/macOS 또는 Mininet 미설치 환경에서 Digital Twin이 실행되지 않아도 최종 `APPROVE`가 나온다.
- 연구 데모에서는 편하지만, 운영 안전성 관점에서는 "검증 통과"와 "검증 생략"이 섞인다.

권장 방향:

- `APPROVE`와 `APPROVE_WITHOUT_TWIN` 분리
- CLI 옵션으로 `--allow-twin-skip-approve` 명시
- 논문 실험에서는 skipped를 pass로 집계하지 않기

---

### Issue 5. Digital Twin rollback 정책이 운영 환경에 위험할 수 있음

위치:

- `endTOend/stage4_twin/twin_verifier.py`
- `endTOend/stage4_twin/onos_client.py`

현재 Twin 검증 과정에서 기존 app flow를 정리하고, 테스트 후 priority 기준 삭제를 수행한다.

영향:

- 전용 테스트 ONOS에서는 괜찮다.
- 운영 ONOS나 공유 ONOS에서는 의도하지 않은 flow 삭제 가능성이 있다.

권장 방향:

- 테스트 전용 app id 또는 cookie/tag 기반으로 배포한 flow만 추적
- rollback policy 도입
  - `ADDITIVE`: 기존 flow 유지 + 새 flow만 추가/삭제
  - `REPLACE`: 동일 범위 flow 교체
  - `FULL_RESET`: 테스트 전용 환경에서만 전체 정리
- XAI가 rollback policy의 영향을 설명하도록 확장

---

### Issue 6. 기존 `experiments/4_integrated_pipeline`는 진정한 end-to-end 검증이 아님

위치:

- `experiments/4_integrated_pipeline/run_pipeline.py`

파일 내부 TODO에도 명시되어 있듯, Stage 3 Digital Twin은 Stage 2에서 생성된 FlowRule을 실제로 전달하지 않고 하드코딩된 DROP rule을 사용한다.

영향:

- 기존 통합 실험 결과를 "완전한 end-to-end"로 주장하기 어렵다.
- 논문에서는 "staged integration" 또는 "partial integration"으로 표현하는 것이 안전하다.

권장 방향:

- Stage 2 valid 결과 중 대표 FlowRule을 Stage 3에 전달
- 최소 3개 intent 유형에 대해 실제 생성 룰 기반 Digital Twin 검증 수행

---

## 5. 드라이런 QA 결과

외부 의존성을 호출하지 않고 다음 경로를 확인했다.

```text
IntentIR
  -> compile_flowrule()
  -> static_validate()
  -> XAIExplainer.explain()
```

확인 결과:

| 샘플 | 결과 |
|---|---|
| block sample: switch 1, src=10.0.0.1, dst=10.0.0.4 | FlowRule 생성, schema validation, XAI decision 정상 |
| forward sample: switch 2, TCP dst 80, in_port=1, out_port=2 | FlowRule 생성, schema validation, XAI decision 정상 |
| device_hint=`s2` | CompileError 발생 |
| 기존 broad forward flow와 새 block flow 비교 | conflict detector 자체는 Imbrication 탐지 |

해석:

- 결정론적 core path는 기본 동작 가능하다.
- conflict detector는 직접 호출하면 동작한다.
- 하지만 CLI/UI에서는 기존 flow를 주입하지 않아 conflict detector가 실제로 쓰이지 않는 상태다.

---

## 6. 우선순위별 개선 계획

### P0. QA 신뢰도 회복

목표: 현재 구현이 문서/논문 주장과 어긋나는 부분을 먼저 줄인다.

작업:

1. `existing_flows=None` 구조 개선
2. `sN` device hint 파싱 지원
3. XAI의 `NOACTION` 표시 오류 수정
4. `skipped` twin 결과를 별도 decision으로 분리
5. 위 4개 항목에 대한 단위 테스트 추가

성공 기준:

- `pytest`로 Stage 2/3/5 핵심 로직 검증 가능
- block rule XAI 요약이 `DROP`으로 표시
- `s1`, `s2`, `switch 1`, `switch second`, `of:...` 모두 정상 파싱
- Digital Twin skipped가 일반 `APPROVE`로 숨겨지지 않음

---

### P1. 논문용 end-to-end 실험 정합성 확보

목표: "진짜 end-to-end"라고 말할 수 있는 실험 루프를 만든다.

작업:

1. LLM/RAG 결과의 `IntentIR` 저장
2. Stage 2에서 생성된 실제 FlowRule을 Stage 4 Twin에 전달
3. 최소 3개 intent 유형 검증
   - block
   - forward
   - qos 또는 TCP/UDP port match
4. 각 run에 대해 다음 로그를 저장
   - original intent
   - parsed IntentIR
   - generated FlowRule
   - static result
   - twin checks
   - XAI report
   - final decision

성공 기준:

- 하드코딩된 DROP rule이 아니라 생성된 FlowRule로 Twin 검증 수행
- 논문 표에 `Intent -> FlowRule -> Static -> Twin -> XAI` 전체 결과 제시 가능

---

### P2. Digital Twin 검증 정밀도 향상

목표: ping pass/fail 수준을 넘어 QoS와 경로 검증을 강화한다.

작업:

1. `iperf3` 기반 대역폭 검증 추가
2. `ovs-appctl ofproto/trace` 기반 path/action trace 추가
3. baseline과 post-deploy 결과 diff 저장
4. regression pair를 1개에서 복수 pair로 확대

성공 기준:

- QoS/forward intent에 대해 실제 Mbps 또는 trace evidence 제공
- XAI report에 "왜 통과/실패했는지"를 숫자와 trace 기반으로 설명 가능

---

### P3. XAI 차별화 강화

목표: 단순 요약을 넘어 논문 기여로 보일 수 있는 XAI 기능을 추가한다.

작업:

1. Confidence score 추가
   - intent parsing confidence
   - static validation confidence
   - twin validation confidence
2. Rollback impact explanation 추가
3. Counterfactual explanation 추가
   - "이 룰이 없으면 어떤 트래픽이 통과/차단되는가?"
4. 설명 레벨 분리
   - brief
   - standard
   - detailed

성공 기준:

- XAI report가 단순 자연어 설명이 아니라 evidence, confidence, rollback impact를 포함
- 논문에서 기존 LLM-to-SDN 연구 대비 차별점으로 주장 가능

---

### P4. 기능 확장

목표: 단순 forward/block/qos를 넘어 더 풍부한 intent를 지원한다.

후보:

1. SFC intent
   - firewall -> IDS -> proxy 체인
2. reroute intent
   - latency/bandwidth 기준 경로 선택
3. load balancing
   - group table 기반 ECMP
4. rate limiting
   - meter table 기반 제한

권장 순서:

1. rate limiting
2. load balancing
3. reroute
4. SFC

이유:

- rate limiting과 load balancing은 ONOS/OpenFlow 객체로 표현이 비교적 명확하다.
- reroute와 SFC는 토폴로지 동기화, 경로 계산, VNF 모델링이 필요해 난이도가 높다.

---

## 7. 추천 실행 순서

### Step 1. 안전성 버그 수정 계획 수립

수정 대상:

- `stage2_flowrule/compiler.py`
- `stage5_xai/explainer.py`
- `pipeline.py`
- `app.py`

예상 작업량:

- 0.5~1일

---

### Step 2. 단위 테스트 추가

테스트 대상:

- device hint parser
- block/forward/qos FlowRule compile
- schema validator
- conflict detector
- XAI action summary
- twin skipped decision policy

예상 작업량:

- 1일

---

### Step 3. 진짜 end-to-end 실험 3개 확정

추천 intent:

```text
1. block all traffic from 10.0.0.1 to 10.0.0.4 on switch 1
2. forward TCP traffic destined to port 80 from switch 1 port 1 to port 2
3. apply queue 1 to UDP traffic from 10.0.0.1 to 10.0.0.4 on switch 1
```

예상 작업량:

- 1~2일

---

### Step 4. 논문용 결과표 정리

표 구성:

| Intent | Parsed IR | Static | Twin | Decision | XAI Evidence |
|---|---|---|---|---|---|

예상 작업량:

- 0.5일

---

### Step 5. 확장 기능 선택

논문 마감 기준 추천:

1. `iperf3` QoS 검증
2. Rollback impact XAI
3. Confidence score

SFC/reroute는 시간이 충분할 때만 진행하는 것이 안전하다.

---

## 8. 최종 판단

현재 프로젝트는 좋은 연구 구조를 갖고 있으며, 핵심 아이디어도 분명하다.

가장 중요한 보완점은 새 기능 추가가 아니라 다음 세 가지다.

1. 실제 CLI/UI에서 Static Validator가 기존 flow와 비교하도록 만들기
2. XAI 설명이 실제 FlowRule semantics와 어긋나지 않게 만들기
3. Digital Twin skipped와 verified pass를 분리해서 논문/운영 신뢰도를 확보하기

이 세 가지를 먼저 정리하면, 이후 `iperf3`, rollback explanation, confidence score를 얹었을 때 논문 기여가 훨씬 또렷해진다.
