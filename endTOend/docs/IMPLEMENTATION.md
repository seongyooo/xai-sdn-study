# End-to-End XAI SDN Pipeline — 구현 설명서

## 전체 구조

자연어 네트워크 인텐트를 입력받아 LLM 해석 → FlowRule 생성 → 정적 검증 →
Digital Twin 시뮬레이션 → XAI 설명 → 실제 ONOS 배포까지 6단계로 처리하는
폐루프형 자동화 파이프라인이다.

```
자연어 인텐트
     │
     ▼
[Stage 1] LLM/RAG → Intent IR
     │
     ▼
[Stage 2] Deterministic Compiler → FlowRule JSON
     │
     ▼
[Stage 3] Static Validator (Schema + Conflict)
     │ REJECT ──────────────────────────┐
     │ PASS                             │
     ▼                                  │
[Stage 4] Digital Twin 검증             │
     │ FAIL ────────────────────────────┤
     │ PASS                             │
     ▼                                  │
[Stage 5] XAI 설명 생성                │
     │                                  │
     ▼                                  ▼
[Stage 6] ONOS 배포              REJECT / 운영자 확인
```

---

## 디렉토리 구조

```
endTOend/
├── pipeline.py              # 메인 CLI 진입점
├── config.py                # 전역 설정 (.env 로드)
├── models/
│   ├── intent_ir.py         # IntentIR + IntentPrediction 데이터 모델 (Pydantic)
│   └── topology.py          # 네트워크 토폴로지 정의 + 엔티티 검증 (B-2)
├── stage1_intent/
│   ├── llm_client.py        # LLM 백엔드 추상화 (Ollama / Gemini)
│   ├── rag.py               # FAISS 기반 RAG
│   └── intent_parser.py     # 자연어 → IntentIR
├── stage2_flowrule/
│   └── compiler.py          # IntentIR → ONOS FlowRule (결정론적)
├── stage3_static/
│   ├── schema_validator.py  # Pydantic 스키마 검증
│   ├── conflict_detector.py # Rule-based 충돌 탐지
│   └── static_validator.py  # 두 모듈 통합 인터페이스
├── stage4_twin/
│   ├── onos_client.py       # ONOS REST API 클라이언트
│   ├── topology.py          # Mininet 다이아몬드 토폴로지
│   └── twin_verifier.py     # 임시 배포 → 검증 → rollback
├── stage5_xai/
│   └── explainer.py         # Evidence-grounded XAI 보고서
├── stage6_deploy/
│   └── deployer.py          # 실제 ONOS 배포
└── logs/                    # 실행 결과 JSON (run_id 기반)
```

---

## 각 Stage 구현 상세

### Stage 1 — LLM/RAG 인텐트 해석 (`stage1_intent/`)

**역할:** 자연어 문자열을 구조화된 `IntentIR` 객체로 변환한다.

#### IntentIR (`models/intent_ir.py`)

LLM과 Compiler 사이의 **controller-neutral 중간 표현**이다.
LLM은 의미만 추출하고, FlowRule 포맷 변환은 코드가 담당한다.

```python
class IntentIR(BaseModel):
    action: Literal["forward", "block", "qos"]
    device_hint: str          # "switch 4", "node 2" 등
    src_ip: Optional[str]     # "10.0.0.1/32" (마스크 없으면 /32 자동 추가)
    dst_ip: Optional[str]
    src_port: Optional[int]
    dst_port: Optional[int]
    ip_proto: Optional[Literal["tcp", "udp", "icmp"]]
    out_port: Optional[int]
    in_port: Optional[int]
    priority: Optional[int]
    vlan_id: Optional[int]
    queue_id: Optional[int]
    eth_type: Optional[Literal["ipv4", "ipv6", "arp"]]  # 기본값 "ipv4"
```

`from_llm_output()` 메서드로 LLM 출력에서 안전하게 파싱한다.
알 수 없는 action 값은 키워드 매핑으로 정규화한다
(`drop/deny/reject` → `block`, `queue/quality` → `qos`).

#### LLMClient (`llm_client.py`)

Ollama와 Gemini API를 동일한 인터페이스로 추상화한다.

| 메서드 | 역할 |
|--------|------|
| `call(system, user)` | JSON 응답 반환 (실패 시 None) |
| `embed(text)` | 임베딩 벡터 반환 |
| `_is_gemini()` | 모델명으로 백엔드 판별 |

- **Ollama**: SSE 스트리밍 파싱, `<think>...</think>` 블록 자동 제거 (qwen3 thinking mode 대응)
- **Gemini**: `response_mime_type="application/json"` 으로 JSON 강제
- **재시도**: 일반 오류 3회 (1s/2s/4s 대기), Gemini 429 Rate Limit은 4회 (30s/60s/120s/180s 대기)

#### RAG (`rag.py`)

Intent2Flow-ONOS.csv의 예시 50개를 임베딩해 FAISS IndexFlatL2에 저장한다.
인텐트 입력 시 의미적으로 유사한 k개 예시를 검색해 프롬프트에 추가한다.

#### IntentParser (`intent_parser.py`)

시스템 프롬프트 + RAG 예시 → LLM 호출 → `IntentIR.from_llm_output()` 순서로 처리한다.
`--no-rag` 플래그로 RAG 없이 LLM 직접 호출도 가능하다.

`topology` 파라미터가 제공되면 **토폴로지 그라운딩**이 활성화된다 (아래 절 참조).
`parse()` 의 반환형이 `IntentIR` 에서 `IntentPrediction` 으로 변경되었다.

---

### 토폴로지 그라운딩 — B-2 구현 (`models/topology.py`)

**목적:** LLM이 토폴로지에 없는 호스트(`h9`, `10.0.0.9`)나 스위치(`switch 7`)를
생성하는 **환각(hallucination)**을 억제하고 탐지한다.

로드맵 항목 B-2에 해당하며, 논문의 "인가된 인벤토리 기반 환각 억제" 기여를 구성한다.

#### 구현 방법

두 단계로 동작한다.

**1단계 — 프롬프트 주입 (사전 억제)**

`NetworkTopology.to_prompt_text()` 가 생성하는 토폴로지 컨텍스트를 LLM 시스템 프롬프트
앞부분에 삽입한다. LLM이 응답을 생성하기 전에 허용된 엔티티 목록을 명시적으로 제시한다.

```
Network topology (ONLY reference entities listed here - do not invent others):
  Hosts: h1=10.0.0.1, h2=10.0.0.2, h3=10.0.0.3, h4=10.0.0.4
  Switches:
    s1 (ports: 1,2,3,4,9)
    s2 (ports: 1,2)
    s3 (ports: 1,2)
    s4 (ports: 1,2,3,4)
  Special: s1 port 9 = firewall/IDS service point (SFC waypoint)
```

**2단계 — 후처리 검증 (사후 탐지)**

LLM이 IR을 반환한 후, Python 코드가 토폴로지 인벤토리와 대조한다.
LLM에 자기 오류 판단을 맡기지 않고 결정론적으로 검증한다.

```python
def check_intent(src_ip, dst_ip, device_hint) -> Optional[tuple[str, str]]:
    if not validate_ip(src_ip):
        return ("unknown_entity", f"src_ip '{ip}' not in topology")
    if not validate_ip(dst_ip):
        return ("unknown_entity", f"dst_ip '{ip}' not in topology")
    if not validate_switch(device_hint):
        return ("unknown_entity", f"device '{hint}' not in topology")
    return None  # 검증 통과
```

검증 실패 시 `IntentPrediction(status="rejected", rejection_reason="unknown_entity")` 반환.

#### NetworkTopology 클래스

| 메서드 | 설명 |
|--------|------|
| `diamond()` | 정적 다이아몬드 토폴로지 반환 (항상 사용 가능) |
| `from_onos(client)` | ONOS REST API 실시간 조회; 연결 실패 시 diamond() 폴백 |
| `validate_ip(ip)` | CIDR 포함 IP가 알려진 호스트 IP인지 확인 |
| `validate_switch(hint)` | "switch 4", "s2", ONOS device_id 등 다양한 형식 지원 |
| `check_intent(src, dst, device)` | 세 필드를 한 번에 검증, 위반 시 `(reason, detail)` 반환 |
| `to_prompt_text()` | LLM 프롬프트에 삽입할 토폴로지 텍스트 생성 |

#### IntentPrediction (`models/intent_ir.py`)

`parse()` 의 반환형으로, 파싱 성공/실패를 명시적으로 표현한다.

```python
class IntentPrediction(BaseModel):
    status: Literal["accepted", "rejected"]
    program: Optional[IntentIR] = None          # accepted 시 IntentIR 포함
    rejection_reason: Optional[Literal[         # rejected 시 사유
        "ambiguous",       # 너무 모호해 특정 액션으로 매핑 불가
        "unknown_entity",  # 토폴로지에 없는 호스트/스위치 참조
        "contradictory",   # 서로 모순되는 요구 (allow + block 동시)
        "unsupported",     # 미지원 기능 (MPLS, multicast 등)
    ]] = None
    rejection_detail: Optional[str] = None      # 상세 설명
```

현재 파이프라인이 탐지하는 사유는 `unknown_entity` 이며, 나머지는 B-1(Rejection 처리)에서 추가 예정이다.

#### 파이프라인 동작 변경

**pipeline.py**

ONOS 연결이 가능하면 `NetworkTopology.from_onos()` 로 실시간 토폴로지를 조회하고,
연결 불가 시 `NetworkTopology.diamond()` 로 폴백한다.
`parse()` 가 `rejected` 를 반환하면 Stage 2~6을 건너뛰고 즉시 REJECT 로 종료한다.

```
Stage 1 LLM 파싱
  ├─ accepted → Stage 2 진행
  └─ rejected → [reason] detail 출력 후 REJECT 종료 (exit 2)
```

**evaluate.py**

`parser_obj.parse()` 가 `IntentPrediction` 을 반환하도록 변경되었다.
accepted 케이스에서 `rejected` 가 반환되면 `parse_fail` 로 집계하고 사유를 로그에 기록한다.

#### 설계 결정: LLM이 아닌 Python으로 검증하는 이유

| 방식 | 장점 | 단점 |
|------|------|------|
| LLM 자기 판단 | 프롬프트만으로 구현 | LLM마다 반응 다름, 재현성 없음, 포맷 변경 필요 |
| Python 후처리 (선택) | 결정론적, 100% 재현, 모델 무관 | 프롬프트 주입과 병행해야 최대 효과 |

두 단계를 조합하여 LLM은 "생성 전 참고" 용으로 토폴로지를 사용하고,
Python은 "생성 후 검증" 역할을 확실히 담당한다.

---

### Stage 2 — FlowRule 컴파일 (`stage2_flowrule/compiler.py`)

**역할:** `IntentIR`을 ONOS REST API 형식의 FlowRule JSON으로 변환한다.
**LLM을 사용하지 않는다** — 동일한 IR은 항상 동일한 FlowRule을 생성한다.

#### device_id 변환

`extract_device_id(device_hint)` 가 자연어 힌트를 ONOS ID로 변환한다.

| 입력 | 출력 |
|------|------|
| `"switch 4"` | `"of:0000000000000004"` |
| `"s3"` | `"of:0000000000000003"` |
| `"switch second"` | `"of:0000000000000002"` |
| `"of:0000000000000001"` | `"of:0000000000000001"` (그대로) |

파싱 실패 시 `CompileError` raise (기본값 fallback 없음).

#### criteria 구성 규칙

| IR 필드 | ONOS criterion |
|---------|---------------|
| `eth_type="ipv4"` | `{"type":"ETH_TYPE","ethType":"0x800"}` (항상 포함) |
| `src_ip` | `{"type":"IPV4_SRC","ip":"..."}` |
| `dst_ip` | `{"type":"IPV4_DST","ip":"..."}` |
| `ip_proto="tcp"` | `{"type":"IP_PROTO","protocol":6}` |
| `dst_port` (tcp) | `{"type":"TCP_DST","tcpPort":...}` |
| `dst_port` (udp) | `{"type":"UDP_DST","udpPort":...}` |
| `in_port` | `{"type":"IN_PORT","port":"..."}` |
| `vlan_id` | `{"type":"VLAN_VID","vlanId":...}` |

#### action → treatment 매핑

| action | treatment |
|--------|-----------|
| `block` | `{"instructions":[{"type":"NOACTION"}]}` (명시적 DROP) |
| `forward` | `{"instructions":[{"type":"OUTPUT","port":"포트번호"}]}` |
| `qos` | OUTPUT + QUEUE instructions |

> **설계 결정**: ONOS REST API에 treatment 없이 POST하면 일부 ONOS 버전에서 DROP이 보장되지 않는다.
> Intent2Flow-ONOS.csv 원본 데이터는 treatment를 생략하지만, 실제 ONOS+OVS 환경에서는
> `NOACTION` instruction을 명시해야 OVS에 `actions=drop` 규칙이 확실히 설치된다.
> action 감지 로직: `treatment.instructions`에 `OUTPUT` 타입이 있으면 forward, 없으면 block.

#### 기본 priority

| action | priority |
|--------|----------|
| block | 50000 |
| forward | 32768 |
| qos | 40000 |

`ir.priority` 가 설정되어 있으면 그 값을 우선 사용한다.

---

### Stage 3 — Static Validator (`stage3_static/`)

**역할:** 생성된 FlowRule의 스키마 유효성과 기존 규칙과의 충돌을 검사한다.

#### Schema Validator (`schema_validator.py`)

Pydantic으로 ONOS FlowRule 구조를 검증한다.

검사 항목:
- `flows` 배열 존재 및 비어있지 않음
- 각 flow에 `deviceId`, `selector`, `selector.criteria` 필수
- **instruction type 화이트리스트** (LLM 환각 방지):
  `OUTPUT`, `DROP`, `NOACTION`, `L2MODIFICATION`, `L3MODIFICATION` 등 허용 목록에 없으면 오류
- **criterion type 화이트리스트**:
  `ETH_TYPE`, `IPV4_SRC`, `IPV4_DST`, `TCP_DST`, `UDP_DST` 등 표준 타입만 허용

#### Conflict Detector (`conflict_detector.py`)

Rule-based로 5가지 충돌 유형을 탐지한다 (LLM 미사용).

| 충돌 유형 | 설명 |
|-----------|------|
| Shadowing | 상위 priority 규칙이 하위 규칙의 match를 완전히 포함 + action 다름 |
| Redundancy | match 동일 + action 동일 (완전 중복) |
| Correlation | match 겹침 + action 다름 |
| Imbrication | 한 규칙이 다른 규칙의 match 부분집합 + action 다름 |
| Generalization | match 포함 관계 + action 같음 |

`criteria_overlap()` 에서 공통 필드가 없을 때 ETH_TYPE 의미적 호환성을 체크한다
(ARP 규칙과 IPv4 주소 필드 규칙은 겹칠 수 없음 — QA에서 발견된 False Positive 수정 반영).

#### Static Validator 통합 (`static_validator.py`)

```
1. validate_schema(flowrule)          → schema_errors 수집
2. detect_conflict(flowrule, existing) → conflicts 수집  (스키마 통과 시만)
3. passed = (schema_errors == 0) AND (conflicts == 0)
```

결과는 `StaticResult` 데이터클래스로 반환된다.

---

### Stage 4 — Digital Twin 검증 (`stage4_twin/`)

**역할:** Mininet 환경에서 FlowRule을 임시 배포하고 실제 동작을 검증한 뒤 rollback한다.

#### 환경 조건

Linux + root + Mininet 설치 세 가지가 모두 충족되어야 실행된다.
하나라도 미충족 시 자동으로 `skipped` 상태를 반환한다.

#### 검증 순서 (`twin_verifier.py`)

1. ONOS 준비 대기 (`wait_until_ready`)
2. **OpenFlow 앱 활성화** (`activate_application`): `openflow-base`, `openflow`, `fwd` 순서로 활성화 — 미활성화 시 스위치가 ONOS에 연결되지 않음
3. 기존 stale flow 정리
4. Mininet 다이아몬드 토폴로지 시작
5. 디바이스 연결 대기 (`wait_for_devices`, 90초)
6. baseline 연결성 확인 (h1↔h4 ping)
7. 후보 FlowRule 임시 배포
8. **flow 설치 대기** (`wait_for_flow`): ONOS에서 해당 priority의 flow가 `ADDED` 상태가 될 때까지 최대 15초 대기
9. 검증 실행:
   - **intent_check**: block이면 대상 pair ping 실패 확인, forward면 성공 확인
   - **regression**: 비대상 host pair (h2↔h3)가 영향받지 않는지 확인
10. 무조건 rollback (성공/실패 무관)
11. Mininet 종료

#### ping 판정 로직

```python
# 버그: "0% packet loss" in "100% packet loss" → True (Python 부분 문자열 매칭)
# 수정: regex로 실제 loss % 추출
m = re.search(r"(\d+)% packet loss", result)
loss_pct = int(m.group(1)) if m else 100
reachable = (loss_pct == 0)
```

> `"0% packet loss"`는 `"100% packet loss"` 문자열의 부분 문자열이다 (위치 2부터 매칭).
> 단순 `in` 연산자 사용 시 block rule이 정상 작동해도 intent_check가 항상 FAIL하는 버그 발생.

#### 토폴로지 (`topology.py`)

다이아몬드 4-switch 구조:

```
h1 - s1 - s2 - s4 - h4
          s3 -/
h2 - s2      h3 - s3
```

---

### Stage 5 — XAI 설명 (`stage5_xai/explainer.py`)

**역할:** 각 스테이지의 결과를 종합하여 운영자가 이해할 수 있는 설명과 APPROVE/REJECT 판정을 생성한다.

#### 결정 로직

```python
twin_passed = twin_result.status in ("passed", "skipped")
decision = "APPROVE" if static_result.passed and twin_passed else "REJECT"
```

#### 설명 구성 방식

| 구성 요소 | 생성 방법 |
|-----------|-----------|
| IntentIR 요약 | 템플릿 기반 (결정론적) |
| FlowRule 요약 | 템플릿 기반 (결정론적) |
| 정적 검증 요약 | `StaticResult.summary()` |
| Twin 결과 요약 | 템플릿 기반 (결정론적) |
| **판정 근거** | LLM 기반 (실패 시 템플릿 fallback) |

자유 형식 LLM 설명이 아닌 **evidence-grounded** 구조를 사용한다.
각 설명 문장은 실제 스테이지 출력(verifier result, rule data)에 연결된 evidence 목록과 함께 저장된다.

#### XAIReport 구조

```python
@dataclass
class XAIReport:
    intent: str           # 원본 인텐트
    ir_summary: str       # Stage1 요약
    flowrule_summary: str # Stage2 요약
    static_summary: str   # Stage3 요약
    twin_summary: str     # Stage4 요약
    decision: str         # "APPROVE" | "REJECT"
    decision_reason: str  # 판정 근거
    evidence: list[dict]  # [{stage, finding, data}, ...]
```

---

### Stage 6 — ONOS 배포 (`stage6_deploy/deployer.py`)

**역할:** APPROVE 판정 시에만 실제 ONOS 컨트롤러에 FlowRule을 배포한다.

- `OnosClient.deploy_flow_rules(flowrule)` 호출
- 배포 전후 `flows()` 차분으로 신규 flow ID를 식별
- 배포 실패 시 `DeployResult(success=False, error=...)` 반환
- `--skip-deploy` 플래그로 실제 배포 없이 파이프라인 전체 테스트 가능

---

## CLI 사용법

```bash
cd endTOend/

# 기본 실행 (Gemini)
python pipeline.py \
  --intent "block all traffic from 10.0.0.1 to 10.0.0.4 on switch 1" \
  --model gemini-3.1-flash-lite

# RAG 없이 빠른 테스트 (임베딩 API 호출 생략)
python pipeline.py \
  --intent "route HTTP traffic from port 1 to port 2 on switch 3" \
  --model gemini-3.1-flash-lite \
  --no-rag

# Digital Twin + 실제 배포 모두 스킵 (정적 검증까지만)
python pipeline.py \
  --intent "..." \
  --model gemini-3.1-flash-lite \
  --no-rag --skip-twin --skip-deploy

# 상세 출력 (FlowRule JSON + 검증 체크 목록)
python pipeline.py --intent "..." --verbose
```

| 플래그 | 설명 |
|--------|------|
| `--model` | LLM 모델명 (기본: .env의 LLM_MODEL) |
| `--rag-k` | RAG 유사 예시 수 (기본: 3) |
| `--no-rag` | RAG 인덱스 구축 스킵, LLM 직접 호출 |
| `--skip-twin` | Stage 4 Digital Twin 검증 스킵 |
| `--skip-deploy` | Stage 6 ONOS 실제 배포 스킵 |
| `--verbose` | FlowRule JSON 및 검증 체크 항목 상세 출력 |

---

## 검증 결과

### 전체 파이프라인 통합 실행 (`logs/20260715T060438Z.json`)

**완전 자동 실행 (Stage 1~6 모두 통과, 실제 ONOS 배포까지 성공):**

```
모델: gemini-3.1-flash-lite
인텐트: "block all traffic from 10.0.0.1 to 10.0.0.4 on switch 1"
플래그: --no-rag
환경: WSL2 (Ubuntu), ONOS Docker, Mininet
```

| Stage | 결과 | 내용 |
|-------|------|------|
| Stage 1 | ✅ PASS | action=block, src=10.0.0.1/32, dst=10.0.0.4/32, device=1 |
| Stage 2 | ✅ PASS | of:0000000000000001, priority=50000, DROP |
| Stage 3 | ✅ PASS | Schema OK, 충돌 없음 |
| Stage 4 | ✅ PASS | baseline OK / intent_check(block 확인) OK / regression OK |
| Stage 5 | ✅ APPROVE | 모든 검사 통과 근거 포함 |
| Stage 6 | ✅ 배포 완료 | flow ID: 50665499140815819 |

```
최종 결정: APPROVE
배포 성공 (1개 flow ID: ['50665499140815819'])
```

---

### 디버깅 과정에서 발견된 버그 및 수정

#### Bug 1: `activate_application()` 메서드 누락

- **증상**: Digital Twin에서 Mininet 스위치가 ONOS에 연결되지 않음 (`ONOS 디바이스 연결 실패`)
- **원인**: `endTOend/stage4_twin/onos_client.py`에 `activate_application()` 메서드 누락. `twin_verifier.py`에서 호출하지만 `AttributeError`가 `except Exception: pass`로 조용히 무시됨
- **수정**: `onos_client.py`에 `activate_application()` 추가

#### Bug 2: `"0% packet loss" in "100% packet loss"` Python 부분 문자열 버그

- **증상**: OVS에 DROP rule이 정상 설치되고 실제로 패킷을 드롭하는데도 intent_check FAIL
- **원인**: `"0% packet loss" in "100% packet loss"` = `True` (파이썬 `in` 연산자는 부분 문자열 검사)
  - "100% packet loss" 문자열의 2번째 위치부터 "0% packet loss"가 매칭됨
- **수정**: regex로 loss percentage 숫자 직접 추출 후 0 여부 비교

#### Bug 3: ONOS block rule treatment 명시 필요

- **증상**: ONOS에서 `ADDED` 상태임에도 OVS의 DROP rule이 실제로 패킷을 처리하지 않는 경우
- **원인**: treatment 없이 POST 시 ONOS 버전에 따라 DROP이 보장되지 않음
- **수정**: `"treatment": {"instructions": [{"type": "NOACTION"}]}` 명시적 추가

#### Bug 4: `wait_for_flow()` 없음으로 인한 race condition

- **원인**: flow를 ONOS에 POST한 직후 바로 ping 테스트를 실행하면, ONOS→OVS 전파 완료 전에 테스트가 수행될 수 있음
- **수정**: `wait_for_flow()` 추가 — 해당 priority의 flow가 `ADDED` 상태가 될 때까지 최대 15초 대기

---

### 이전 실행 로그 (`logs/20260715T044205Z.json`)

```
모델: gemini-3.1-flash-lite
인텐트: "block all traffic from 10.0.0.1 to 10.0.0.4 on switch 1"
플래그: --no-rag --skip-twin --skip-deploy
```

**Stage 1 출력 (IntentIR):**
```json
{
  "action": "block",
  "device_hint": "switch 1",
  "src_ip": "10.0.0.1/32",
  "dst_ip": "10.0.0.4/32",
  "eth_type": "ipv4"
}
```
LLM이 `block`, `switch 1`, IP 주소 두 개를 정확히 추출했다.

**Stage 2 출력 (FlowRule):**
```json
{
  "flows": [{
    "priority": 50000,
    "timeout": 0,
    "isPermanent": "true",
    "deviceId": "of:0000000000000001",
    "selector": {
      "criteria": [
        {"type": "ETH_TYPE", "ethType": "0x800"},
        {"type": "IPV4_SRC", "ip": "10.0.0.1/32"},
        {"type": "IPV4_DST", "ip": "10.0.0.4/32"}
      ]
    }
  }]
}
```
`block` 이므로 `treatment` 없음 → ONOS 암묵적 DROP. `device_hint="switch 1"` →
`of:0000000000000001` 변환 정확.

**Stage 3 출력:**
```
Schema OK | 충돌 없음 → PASS
```
3개 criterion 모두 화이트리스트 통과. instruction type 없음(block rule)이므로 환각 오류 없음.

**Stage 5 출력 (XAI):**
```
최종 결정: APPROVE
판정 근거: 해당 FlowRule은 정적 검증 과정에서 스키마 오류나 기존 규칙과의
충돌이 발견되지 않아 안전한 것으로 확인되었습니다. Digital Twin 검증은
생략되었으며, 최종적으로 배포가 승인되었습니다.
```

### Stage별 독립 검증 (mock 테스트)

LLM 없이 Stage 2~5를 직접 검증했다.

```python
# IntentIR 하드코딩으로 Stage 1 우회
ir = IntentIR(action='block', device_hint='switch 1',
              src_ip='10.0.0.1/32', dst_ip='10.0.0.4/32')

flowrule = compile_flowrule(ir)       # Stage 2: criteria 3개, DROP
static   = validate(flowrule, [])     # Stage 3: Schema OK, 충돌 없음 → PASS
twin     = TwinResult(status='skipped', reason='Windows 환경')
report   = XAIExplainer().explain(...)  # Stage 5: APPROVE
```

모든 Stage가 독립적으로 정상 동작했다.

### 검증 항목 요약

| 항목 | 결과 |
|------|------|
| LLM → IntentIR 파싱 (block intent) | ✅ 정확 (action, device, IP 모두 추출) |
| device_hint → ONOS ID 변환 | ✅ `switch 1` → `of:0000000000000001` |
| block rule FlowRule 생성 | ✅ NOACTION treatment, criteria 3개 |
| Pydantic 스키마 검증 통과 | ✅ PASS |
| 충돌 탐지 (기존 rule 없음) | ✅ 충돌 없음 |
| Digital Twin baseline 연결성 | ✅ h1→h4 ping 성공 확인 |
| Digital Twin intent_check (block) | ✅ FlowRule 배포 후 h1→h4 ping 100% loss 확인 |
| Digital Twin regression | ✅ h2→h3 영향 없음 확인 |
| OVS DROP rule 실제 설치 확인 | ✅ `ovs-ofctl`: `priority=50000 actions=drop` |
| XAI APPROVE 판정 | ✅ 모든 검사 통과 근거 포함 |
| 실제 ONOS 배포 | ✅ flow ID `50665499140815819` |
| 실행 로그 JSON 저장 | ✅ `logs/{run_id}.json` |
| Windows 환경 Stage 4 자동 skip | ✅ 오류 없이 skipped 반환 |
| Gemini 429 재시도 로직 | ✅ 30/60/120/180s 대기 |
| 전체 파이프라인 exit 0 | ✅ APPROVE 시 정상 종료 |

---

## 설계 결정 및 근거

### LLM을 Stage 2에서 제외한 이유

기존 `experiments/4_integrated_pipeline`에서는 LLM이 FlowRule을 직접 생성했다.
이 방식은 QA 과정에서 `PUSH_VLAN`, `SET_VLAN_ID` 같은 존재하지 않는
instruction type을 생성하는 **환각** 문제가 확인됐다.

Stage 2를 결정론적 컴파일러로 분리하면:
- 동일 IR → 항상 동일 FlowRule (재현성)
- LLM이 생성할 수 없는 환각 instruction type 원천 차단
- 컨트롤러가 바뀌어도 컴파일러만 수정하면 됨

### Rule-based 충돌 탐지를 선택한 이유

LLM 기반 충돌 탐지는 API 실패 시 결과가 없고, 재현성이 없으며, 지연이 크다.
Rule-based는 결정론적이고 빠르며 Static Validator의 역할에 적합하다.
LLM은 Stage 5에서 충돌 설명(why/impact/remedy) 생성에만 사용한다.

### Evidence-grounded XAI를 선택한 이유

자유 형식 LLM 설명은 실제 verifier 결과와 무관한 unsupported claim을 포함할 수 있다.
각 설명 문장을 실제 stage 출력 데이터에 연결하는 evidence 구조를 쓰면
설명의 신뢰도를 높이고 논문의 RQ6을 정량적으로 측정할 수 있다.

---

## 토폴로지 에디터 (`static/` — UI 기능)

### 개요

실제 OVS/ONOS 인프라 없이도 네트워크 토폴로지를 UI에서 직접 정의할 수 있는
D3.js 기반 드래그앤드롭 에디터다. 사용자가 배치한 토폴로지는 파이프라인 전체에
적용되며, ONOS가 오프라인 상태일 때 시각화 폴백으로도 동작한다.

**배경:** 실제 SDN 스위치나 OVS 환경은 고가 장비 또는 별도 인프라가 필요하다.
에디터를 통해 임의 토폴로지를 사전 정의하면 실제 장비 없이 다양한 실험이 가능하다.

---

### 아키텍처

```
[UI Edit Mode]
  사용자 조작 (드래그/클릭)
       │
       ▼
  editor state (app.js)
  { nodes: [...], links: [...] }
       │ POST /api/topology/custom
       ▼
  data/custom_topology.json  ←──── 영속 저장
       │
       ├──► GET /api/topology        → D3 시각화 (ONOS 폴백)
       └──► _run_pipeline()          → NetworkTopology.from_custom_file()
                                         └─ Stage 1~6 파이프라인에 반영
```

---

### UI 구성 (`static/index.html`, `static/app.js`)

#### 모드 전환

우측 토폴로지 패널 헤더의 **Edit 버튼**으로 라이브 모드 ↔ 에디터 모드를 전환한다.

| 라이브 모드 | 에디터 모드 |
|------------|------------|
| ONOS 토폴로지 자동 폴링 (1초) | 폴링 중단, 편집 캔버스 활성화 |
| Refresh 배지 표시 | 툴바 + Properties 패널 표시 |
| Metrics / Flow Table 표시 | Properties 패널로 교체 |

모드 진입 시 `clearTopologyGraph()` 로 기존 D3 요소를 완전히 제거한 뒤
해당 모드의 렌더링 함수를 호출한다. `fetchTopology()` 는 `editor.active` 가
`true` 일 때 즉시 반환하여 라이브 업데이트가 에디터를 덮어쓰지 않도록 한다.

#### 툴바 5개 도구

| 아이콘 | 도구 | 동작 |
|--------|------|------|
| ↖ | Select | 노드 클릭으로 선택, 드래그로 이동 |
| ⬡ | Switch | 캔버스 빈 공간 클릭 → 스위치 노드 배치 |
| ◎ | Host | 캔버스 빈 공간 클릭 → 호스트 노드 배치 |
| ╌ | Link | 노드 A 클릭 → 노드 B 클릭 → 링크 연결 |
| ✕ | Delete | 노드/링크 클릭으로 삭제 |

**Link 도구 Ghost Line:** 첫 번째 노드 클릭 후 마우스 이동 시 점선(`#ghost-link`)이
커서를 따라 표시되어 연결 방향을 시각적으로 안내한다. 동일 노드 재클릭 또는
빈 캔버스 클릭 시 취소된다. 동일 노드 쌍 중복 링크는 자동 방지된다.

#### Properties 패널

노드 선택 시 (Select 도구) 우측 하단에 속성 편집 폼이 나타난다.

| 노드 종류 | 편집 가능 필드 |
|-----------|--------------|
| Switch | Label, DPID (16자리 hex) |
| Host | Label, IP Address, MAC Address |
| 공통 | 연결된 링크 목록 (대역폭 Mbps 수정, 링크 삭제) |

모든 필드는 실시간으로 캔버스에 반영된다 (`input` 이벤트 → `renderEditorGraph()`).

#### 기본 토폴로지

Edit 모드 최초 진입 시 저장된 커스텀 토폴로지가 없으면
**다이아몬드 4-스위치 토폴로지** (Diamond)를 기본값으로 로드한다.

```
h1(10.0.0.1) ─┐         ┌─ h3(10.0.0.3)
               S1─(1M)─S2─(1M)─S4
h2(10.0.0.2) ─┘  ╲(10M)╱      └─ h4(10.0.0.4)
                   S3
```

스위치 자동 DPID: `0000000000000001` ~ `000000000000000N`
호스트 자동 IP: `10.0.0.N`, MAC: `00:00:00:00:00:0N`

#### Apply 동작

**Apply** 클릭 시:
1. `POST /api/topology/custom` 으로 현재 에디터 상태를 저장
2. 현재 토폴로지 기반으로 **Example Chips 자동 갱신**
   (호스트 IP와 스위치 번호를 읽어 Block / Forward / QoS 예시 인텐트 생성)
3. 에디터 모드 종료 → 라이브 모드로 복귀
4. `topoSnapshot = null` 로 즉시 재렌더 트리거

---

### D3.js 렌더링 분리

기존 라이브 모드(`updateTopology`)와 에디터 모드(`renderEditorGraph`)는
동일한 SVG를 공유하지만 선택자로 격리된다.

| 구분 | 선택자 | 설명 |
|------|--------|------|
| 라이브 노드 | `g.live-node` | ONOS 실시간 데이터 |
| 에디터 노드 | `g.ed-node` | 사용자 편집 데이터 |
| 라이브 링크 | `line` (직접) | D3 join |
| 에디터 링크 | `g.ed-link` | `<g>` 래퍼 + 히트 영역 포함 |

모드 전환 시 `clearTopologyGraph()` 가 두 레이어를 모두 비운다.
에디터의 D3 force simulation은 사용하지 않으며, 모든 노드가 `fx`/`fy` 고정 위치를 갖는다.
드래그 시 `d.x`/`d.y` 를 직접 수정하고 `renderEditorGraph()` 를 재호출한다.

---

### 데이터 포맷 (`data/custom_topology.json`)

```json
{
  "switches": [
    { "id": "s1", "label": "S1", "dpid": "0000000000000001", "x": 116, "y": 95 },
    { "id": "s2", "label": "S2", "dpid": "0000000000000002", "x":  96, "y": 180 }
  ],
  "hosts": [
    { "id": "h1", "label": "H1", "ip": "10.0.0.1", "mac": "00:00:00:00:00:01", "x": 41, "y": 70 }
  ],
  "links": [
    { "id": "l1", "source": "h1", "target": "s1", "bw": 100 },
    { "id": "l5", "source": "s1", "target": "s2", "bw": 1 }
  ]
}
```

- `id`: 에디터 내부 식별자 (단순 문자열)
- `dpid`: 16자리 hex, ONOS device_id 변환 시 `of:{dpid}` 형식
- `bw`: 링크 대역폭 (Mbps), 캔버스에 레이블로 표시

---

### API 엔드포인트 (`api.py`)

#### `GET /api/topology/custom`

저장된 커스텀 토폴로지 JSON을 그대로 반환한다.
파일이 없으면 빈 객체 `{}` 반환.

#### `POST /api/topology/custom`

에디터에서 Apply 시 호출된다. Request body를
`data/custom_topology.json` 에 저장하고 `{"ok": true}` 반환.

#### `GET /api/topology` (수정)

ONOS 연결 실패 시 커스텀 토폴로지를 D3 포맷으로 변환하여 반환한다.

변환 규칙 (`_custom_topo_as_d3`):
- 스위치 노드 ID: `s1` → `of:0000000000000001`
- 호스트 노드 ID: 그대로 유지 (`h1`)
- 링크: 스위치 ID를 `of:` 포맷으로 치환
- `_source: "custom"` 필드를 포함해 프론트엔드에서 구분 가능

```
ONOS 응답 정상 → ONOS 데이터 반환
ONOS 오프라인 → custom_topology.json 존재 시 D3 변환 반환
              → 파일 없으면 error 반환
```

---

### 파이프라인 통합

#### `_run_pipeline()` (api.py) 수정

```python
custom_topo = _load_custom_topology()
topology = (
    NetworkTopology.from_custom_file(custom_topo)
    if custom_topo
    else NetworkTopology.diamond()
)
```

커스텀 토폴로지가 저장되어 있으면 그것을 사용하고,
없으면 기존 Diamond 정적 토폴로지로 폴백한다.

#### `NetworkTopology.from_custom_file()` (models/topology.py)

커스텀 토폴로지 dict → `NetworkTopology` 변환 메서드.

```python
@classmethod
def from_custom_file(cls, data: dict) -> "NetworkTopology":
    hosts    = { h["id"]: h.get("ip", "") for h in data["hosts"] }
    switches = { sw["id"]: f"of:{sw['dpid']}" for sw in data["switches"] }
    # 링크에서 스위치별 포트 번호 순번 부여
    for lnk in data["links"]:
        for node_id in (lnk["source"], lnk["target"]):
            if node_id in switches:
                ports[switches[node_id]].append(port_counter[...] + 1)
    return cls(hosts=hosts, switches=switches, ports=ports)
```

파이프라인의 토폴로지 그라운딩 (B-2), 인텐트 검증, 프롬프트 주입 모두
커스텀 토폴로지 기반으로 동작한다.

---

### 설계 결정

#### OVS 직접 읽기 대신 UI 에디터를 선택한 이유

| 방식 | 장점 | 단점 |
|------|------|------|
| OVS 직접 읽기 | 실제 네트워크 반영 | 실제 SDN 스위치 또는 OVS 설치 필요, Windows 미지원 |
| ONOS REST API | 자동 토폴로지 발견 | ONOS 실행 환경 필요 |
| **UI 에디터 (선택)** | 환경 독립적, 즉시 실험 가능 | 수동 입력 필요 |

논문 개발 단계에서 라즈베리파이나 실제 SDN 장비 없이 다양한 토폴로지를
실험할 수 있다는 점에서 현실적인 접근이다. ONOS가 연결되면 라이브 모드로
자동 전환되므로 실제 환경 연동 시 추가 수정 없이 사용 가능하다.

#### D3 force simulation을 에디터에서 비활성화한 이유

라이브 모드에서는 힘-지향 레이아웃이 자동 배치에 유용하지만,
에디터에서는 사용자가 배치한 위치가 즉시 고정되어야 한다.
simulation의 alpha decay로 위치가 계속 변하면 정밀한 배치가 불가능하다.
에디터는 `fx`/`fy` 고정 좌표만 사용하고 simulation을 생략했다.

#### 노드 선택자 분리 (`g.live-node` vs `g.ed-node`)

모드 전환 없이 라이브 업데이트와 에디터가 동일 SVG를 공유할 경우,
`selectAll('g')` 가 두 레이어를 모두 선택해 데이터 바인딩이 충돌할 수 있다.
클래스로 명시적 격리하고 `clearTopologyGraph()` 로 전환 시 완전히 비움으로써
레이어 간 간섭을 완전히 제거했다.
