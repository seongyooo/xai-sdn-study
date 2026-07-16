# 논문 작성 방향 (초안)

> 제출 대상: KICS 제7회 한국 AI 학술대회 (마감 2026-08-24)

---

## 제안 제목

**"LLM 기반 SDN 네트워크 인텐트 자동화를 위한 XAI 통합 파이프라인 설계"**

(부제 후보: Intent IR 중간 표현과 Digital Twin 검증을 중심으로)

---

## 핵심 주장 (논문이 답할 질문)

> 자연어 네트워크 인텐트를 안전하게 ONOS FlowRule로 변환하려면 어떤 구조가 필요한가?
> LLM의 환각(hallucination) 문제를 어떻게 억제하고, 결과를 운영자에게 설명할 수 있는가?

---

## 기여 (Contributions)

| # | 기여 내용 | 구현 위치 |
|---|----------|----------|
| C1 | **Intent IR** — LLM과 컨트롤러를 분리하는 controller-neutral 중간 표현 설계 | `models/intent_ir.py` |
| C2 | **결정론적 컴파일러** — 동일 IR은 항상 동일 FlowRule 생성, LLM 환각 원천 차단 | `stage2_flowrule/compiler.py` |
| C3 | **Rule-based 정적 검증** — Shadowing·Redundancy 등 5종 충돌을 LLM 없이 탐지 | `stage3_static/` |
| C4 | **Digital Twin 검증 루프** — Mininet+ONOS 환경에서 임시 배포 → 검증 → rollback | `stage4_twin/` |
| C5 | **Evidence-grounded XAI** — 각 설명 근거를 실제 stage 출력 데이터에 연결 | `stage5_xai/explainer.py` |

---

## 논문 구조 (6페이지 기준)

### 1. 서론 (~1p)
- SDN 운영자가 자연어로 정책을 표현하고 싶어한다
- LLM으로 직접 FlowRule을 생성하면 환각 오류 발생 (실제 사례: `PUSH_VLAN` 같은 없는 instruction type)
- 기존 연구: Intent2Flow, NetIntent 등은 변환 정확도만 측정, **안전성·설명성 부재**
- 본 논문의 접근: 6단계 파이프라인 + XAI + Digital Twin

### 2. 관련 연구 (~0.5p)
- IBNBench, NetIntent (LLM 기반 FlowRule 생성)
- SDN 충돌 탐지 (ONOS conflict detection)
- Network Digital Twin (Mininet 기반 검증)

### 3. 시스템 설계 (~2p)
- 전체 파이프라인 아키텍처 그림
- Intent IR 설계 근거 (C1)
- 결정론적 컴파일러와 LLM 역할 분리 (C2)
- 정적 검증 5종 충돌 유형 표 (C3)
- Digital Twin 검증 시퀀스 다이어그램 (C4)
- XAI evidence 구조 (C5)

### 4. 구현 (~0.5p)
- 환경: ONOS 2.7 Docker + Mininet + Gemini API
- 다이아몬드 토폴로지 (s1-s4, h1-h4)
- RAG: Intent2Flow-ONOS.csv 50개 예시, FAISS IndexFlatL2

### 5. 평가 (~1.5p)

#### 5.1 Intent 파싱 정확도 (C1, C2)
- Intent2Flow-ONOS.csv 기반 테스트셋 구성
- LLM 직접 생성 vs IR+컴파일러 방식 FlowRule 정확도 비교
- 환각 발생률 (없는 instruction type) 측정

#### 5.2 정적 검증 충돌 탐지율 (C3)
- FlowConflict-ONOS.csv (실험2에서 이미 수행)
- 5종 충돌 유형별 탐지 정밀도/재현율

#### 5.3 Digital Twin 검증 (C4)
- block intent 3종 + forward intent 3종 테스트
- intent_check PASS/FAIL 결과
- baseline/regression 유지 확인

#### 5.4 XAI 설명 충실도 (C5)
- 각 결정 근거가 실제 검증 결과에 연결되는지 수동 평가
- (가능하면) 운영자 이해도 간단 설문

### 6. 결론 (~0.5p)
- 6단계 파이프라인으로 LLM 환각 억제 + 안전성 검증 + 설명성 확보
- 향후: 멀티 컨트롤러 지원, 강화학습 기반 자동 복구

---

## 지금 당장 해야 할 것

1. **평가 실험 설계** — 비교 베이스라인 (LLM 직접 생성) 구현
2. **테스트셋 구성** — Intent2Flow-ONOS.csv에서 train/test 분리
3. **수치 결과 생성** — 위 5.1~5.4 표 채우기
4. **그림 제작** — 파이프라인 아키텍처, Digital Twin 시퀀스

---

## 강조할 차별점

기존 연구와 비교해서 이 논문만의 포인트:

- **IR 분리**: LLM은 의미만 추출, 포맷 변환은 코드 담당 → 재현성 보장
- **검증 루프**: "생성"만이 아닌 "생성 → 검증 → 설명" 전 과정 통합
- **Evidence-grounded XAI**: 설명 근거가 실제 verifier 출력에 연결 (free-form LLM 설명 아님)
