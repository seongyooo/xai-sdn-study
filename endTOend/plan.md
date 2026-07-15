# End-to-End XAI SDN 자동화 시스템 구현 계획

## 시스템 개요

네트워크 운영자가 자연어로 의도(intent)를 입력하면, LLM/RAG가 이를 해석하고
FlowRule을 생성한 뒤 정적 검증 → Digital Twin 시뮬레이션 → XAI 설명을 거쳐
안전한 경우에만 실제 ONOS 컨트롤러에 배포하는 폐루프형 자동화 파이프라인.

```
[사용자 자연어 입력]
        │
        ▼
[Stage 1] LLM/RAG 인텐트 해석
        │
        ▼
[Stage 2] SDN 정책 후보 생성 (FlowRule JSON)
        │
        ▼
[Stage 3] Static Validator
        │ REJECT ──────────────────────────┐
        │ PASS                             │
        ▼                                  │
[Stage 4] Digital Twin 시뮬레이션          │
        │ FAIL ────────────────────────────┤
        │ PASS                             │
        ▼                                  │
[Stage 5] XAI 설명 생성                   │
        │                                  │
        ▼                                  │
[Stage 6] ONOS 실제 배포                  │
        │                                  │
        ▼                                  ▼
    [APPROVE]                    [REJECT / 운영자 확인 요청]
```

---

## 디렉토리 구조

```
endTOend/
├── plan.md                  # 이 파일
├── pipeline.py              # 메인 실행 진입점 (CLI)
├── config.py                # 환경 변수, 모델명, URL 등 전역 설정
│
├── stage1_intent/
│   ├── __init__.py
│   ├── llm_client.py        # Ollama / Gemini API 추상화
│   ├── rag.py               # FAISS 기반 RAG (Intent2Flow 예시 검색)
│   └── intent_parser.py     # 자연어 → Intent IR (중간 표현)
│
├── stage2_flowrule/
│   ├── __init__.py
│   └── compiler.py          # Intent IR → ONOS FlowRule JSON (결정론적 변환)
│
├── stage3_static/
│   ├── __init__.py
│   ├── schema_validator.py  # Pydantic 스키마 검증
│   ├── conflict_detector.py # Rule-based 충돌 탐지 (Shadowing/Redundancy 등)
│   └── static_validator.py  # 위 두 모듈을 묶는 통합 인터페이스
│
├── stage4_twin/
│   ├── __init__.py
│   ├── onos_client.py       # ONOS REST API 클라이언트
│   ├── topology.py          # Mininet 토폴로지 정의
│   └── twin_verifier.py     # 임시 배포 → 검증 → rollback
│
├── stage5_xai/
│   ├── __init__.py
│   └── explainer.py         # 각 스테이지 판단 근거를 자연어로 설명
│
├── stage6_deploy/
│   ├── __init__.py
│   └── deployer.py          # APPROVE 시 실제 ONOS 배포
│
├── models/
│   └── intent_ir.py         # Intent IR 데이터 모델 (dataclass / Pydantic)
│
├── logs/                    # run_id 기반 실행 로그 (자동 생성)
├── data/
│   └── examples/            # RAG용 Intent2Flow 예시 CSV
└── results/                 # 실험 결과 JSON (자동 생성)
```

---

## 각 Stage 상세 설계

### Stage 1 — LLM/RAG 인텐트 해석

**입력:** 자연어 문자열  
**출력:** Intent IR (controller-neutral 중간 표현)

Intent IR 필드:
```json
{
  "action": "forward | block | qos",
  "device_hint": "switch 번호 또는 이름",
  "src_ip": "x.x.x.x/mask | null",
  "dst_ip": "x.x.x.x/mask | null",
  "src_port": "정수 | null",
  "dst_port": "정수 | null",
  "ip_proto": "tcp | udp | icmp | null",
  "out_port": "정수 | null",
  "priority": "정수 | null",
  "vlan_id": "정수 | null",
  "queue_id": "정수 | null",
  "eth_type": "ipv4 | ipv6 | arp | null"
}
```

동작 방식:
- RAG: Intent2Flow-ONOS.csv에서 의미적으로 유사한 예시 k개 검색 (FAISS)
- LLM: 시스템 프롬프트 + RAG 예시 + 사용자 입력 → Intent IR JSON 생성
- 모델: Ollama (기본 qwen3:8b) / Gemini API (선택)

---

### Stage 2 — FlowRule 생성 (Deterministic Compiler)

**입력:** Intent IR  
**출력:** ONOS FlowRule JSON

- Intent IR 필드를 규칙 기반으로 ONOS JSON으로 변환 (LLM 미사용)
- `action=block`이면 `treatment` 필드 생략
- `device_hint`에서 switch ID 추출 (정규식 + 서수 매핑)
- 변환 실패 시 즉시 REJECT (LLM 재시도 없음)

LLM을 사용하지 않는 이유: 동일 IR → 동일 FlowRule 보장 (결정론적), 환각 방지

---

### Stage 3 — Static Validator

**입력:** FlowRule JSON  
**출력:** `{valid: bool, errors: [], conflicts: []}`

검사 항목:
1. **Schema 검증** (Pydantic): 필수 필드, 허용 값, instruction type 화이트리스트
2. **Rule-based 충돌 탐지**: 현재 ONOS에 배포된 기존 FlowRule과 대조
   - Shadowing, Redundancy, Correlation, Imbrication, Generalization
3. **Feasibility 검사**: 존재하지 않는 port/device 참조 여부

판정:
- 오류 있음 → `REJECT` (Stage 4 진입 차단)
- 경고만 있음 → `WARN` (Stage 4 진입 허용, XAI에 기록)
- 이상 없음 → `PASS`

---

### Stage 4 — Digital Twin 시뮬레이션

**입력:** FlowRule JSON  
**출력:** `{passed: bool, checks: {}, evidence: {}}`

동작 순서:
1. Production ONOS에서 현재 토폴로지/플로우 snapshot 수집
2. Validation Twin(별도 Mininet 인스턴스)에 snapshot 복제
3. 후보 FlowRule 임시 배포
4. 자동화 검증:
   - **Reachability**: 의도한 경로로 패킷이 전달되는가
   - **Isolation**: 차단 대상 트래픽이 실제로 차단되는가
   - **Regression**: 기존 정상 트래픽이 영향받지 않는가
   - **Link Failure** (선택): 단일 링크 장애 시 동작 확인
5. 임시 배포 rollback (성공/실패 무관)

판정:
- 전체 PASS → Stage 5 진행
- 하나라도 FAIL → `REJECT` + evidence 구조화

---

### Stage 5 — XAI 설명 생성

**입력:** 전 스테이지의 판단 결과 (Intent IR, FlowRule, 정적 검증 결과, Twin 결과)  
**출력:** 운영자가 읽을 수 있는 자연어 설명 + 근거 JSON

설명 구성:
- **인텐트 해석 결과**: LLM이 어떻게 이해했는가
- **생성된 규칙 요약**: 어떤 FlowRule이 만들어졌는가
- **정적 검증 근거**: 어떤 충돌/오류가 발견되었는가 (발견된 경우)
- **Twin 검증 결과**: 어떤 테스트가 통과/실패했는가
- **최종 판정 이유**: APPROVE / REJECT 근거

자유 형식 LLM 설명이 아닌 **evidence-grounded** 방식:
각 설명 문장에 해당 evidence (verifier output, rule diff, log)가 연결됨

---

### Stage 6 — 실제 ONOS 배포

**입력:** FlowRule JSON + APPROVE 판정  
**출력:** 배포 성공/실패 + flow ID

- Stage 3·4 모두 PASS일 때만 실행
- ONOS REST API (`POST /onos/v1/flows`)로 배포
- 배포 후 flow 상태 확인 (ADDED 상태 검증)
- 실패 시 자동 삭제 시도

---

## 실행 방법 (목표 인터페이스)

```bash
# 기본 실행 (Ollama)
python pipeline.py --intent "block all traffic from 10.0.0.1 to 10.0.0.4 on switch 1"

# Gemini API 사용
GOOGLE_API_KEY=... python pipeline.py \
  --intent "route HTTP traffic from port 1 to port 2 on switch 3" \
  --model gemini-2.0-flash

# Digital Twin 스킵 (빠른 정적 검증만)
python pipeline.py --intent "..." --skip-twin

# 결과 상세 출력
python pipeline.py --intent "..." --verbose
```

출력 예시:
```
[Intent]  "block all traffic from 10.0.0.1 to 10.0.0.4 on switch 1"

[Stage 1] 인텐트 해석 완료
          action=block, src=10.0.0.1/32, dst=10.0.0.4/32, device=switch 1

[Stage 2] FlowRule 생성 완료
          deviceId=of:0000000000000001, priority=50000, selector=...

[Stage 3] 정적 검증 PASS
          schema OK | 충돌 없음

[Stage 4] Digital Twin 검증 PASS (3/3)
          reachability OK | isolation OK | regression OK

[Stage 5] XAI 설명
          "이 규칙은 switch 1에서 10.0.0.1→10.0.0.4 ICMP 트래픽을 DROP합니다.
           정적 충돌 없음. Twin에서 h2→h3 기존 경로 영향 없음 확인."

[Stage 6] ONOS 배포 성공
          flow_id=...

[결과] APPROVE
```

---

## 구현 순서

| 순서 | 작업 | 참조 |
|------|------|------|
| 1 | `config.py`, `models/intent_ir.py` | - |
| 2 | `stage1_intent/llm_client.py` + `rag.py` | experiments/1_netintent_baseline |
| 3 | `stage1_intent/intent_parser.py` | 신규 설계 |
| 4 | `stage2_flowrule/compiler.py` | 신규 설계 (결정론적) |
| 5 | `stage3_static/schema_validator.py` | experiments/2_static_validator/validator.py |
| 6 | `stage3_static/conflict_detector.py` | experiments/2_static_validator/rule_based_detector.py |
| 7 | `stage4_twin/onos_client.py` + `topology.py` | experiments/3_digital_twin |
| 8 | `stage4_twin/twin_verifier.py` | experiments/3_digital_twin/experiment.py |
| 9 | `stage5_xai/explainer.py` | experiments/2_static_validator/explainer.py |
| 10 | `stage6_deploy/deployer.py` | experiments/3_digital_twin/onos_client.py |
| 11 | `pipeline.py` (전체 연결) | experiments/4_integrated_pipeline |
| 12 | 로깅, 결과 저장, CLI 인자 정리 | - |

---

## 기존 실험과의 관계

| 기존 실험 | 재사용 범위 |
|-----------|-------------|
| `experiments/1_netintent_baseline` | RAG 인덱스 구축, LLM 호출, Intent2Flow 데이터셋 |
| `experiments/2_static_validator` | Pydantic 스키마 검증, rule-based 충돌 탐지 로직 |
| `experiments/3_digital_twin` | OnosClient, Mininet 토폴로지, 검증 시나리오 |
| `experiments/4_integrated_pipeline` | 파이프라인 연결 구조, 결과 저장 형식 |

기존 코드를 직접 임포트하지 않고, 로직을 **재작성**하여 결합.
(임포트 충돌, 경로 의존성 문제 방지)

---

## 로그 형식 (run_id 기반)

매 실행마다 `logs/` 아래에 JSON 파일 저장:

```json
{
  "run_id": "20260715T120000Z",
  "git_commit": "a53a8d5",
  "model": "qwen3:8b",
  "intent": "block all traffic from 10.0.0.1 to 10.0.0.4 on switch 1",
  "intent_ir": { ... },
  "flowrule": { ... },
  "static_validation": { "valid": true, "errors": [], "conflicts": [] },
  "twin_result": { "passed": true, "checks": { ... } },
  "xai_report": { "summary": "...", "evidence": [ ... ] },
  "decision": "APPROVE",
  "deployed_flow_id": "...",
  "execution_time_sec": 12.4
}
```

---

## 다음 단계

1. `config.py` + `models/intent_ir.py` 작성
2. `stage1_intent/` 구현
3. `stage2_flowrule/compiler.py` 구현
4. `stage3_static/` 구현 (기존 rule_based_detector 로직 이식)
5. `stage4_twin/` 구현 (기존 experiment.py 로직 이식)
6. `stage5_xai/` + `stage6_deploy/` 구현
7. `pipeline.py`로 전체 연결
8. 인텐트 60개 데이터셋으로 실험 실행
