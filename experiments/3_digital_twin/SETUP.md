# 실험 3 환경 설정 기록

## 환경

- OS: Windows 11 (Build 26200)
- WSL: Ubuntu-22.04 (WSL 2.7.10)
- Docker: Docker Desktop (WSL2 backend)

---

## 1. WSL2 네트워킹 모드 변경 (NAT)

### 문제
WSL 2.7+이 Windows 11에서 자동으로 **mirrored 모드**로 동작.
mirrored 모드에서 Docker Desktop 포트 포워딩 프록시가 Windows 측 리스너를 생성하지 않아
`localhost:8181` 접근 불가.

**증상 확인:**
```bash
ip addr
# eth0: state DOWN, loopback0 UP, eth1에 Windows와 동일한 IP → mirrored 모드
```

### 해결
`C:\Users\seonl\.wslconfig` 파일 생성:
```ini
[wsl2]
networkingMode=NAT
```

적용 방법 (순서 중요):
1. Docker Desktop 트레이 아이콘 우클릭 → **Quit Docker Desktop**
2. PowerShell에서: `wsl --shutdown`
3. Docker Desktop 재실행 (완전히 뜰 때까지 2~3분 대기)

---

## 2. Docker credential 오류 수정

### 문제
```
error getting credentials - err: fork/exec /usr/bin/docker-credential-desktop.exe: exec format error
```

### 해결
WSL 터미널에서:
```bash
echo '{}' > ~/.docker/config.json
```

---

## 3. ONOS 컨테이너 실행

```bash
docker run -d --name onos -p 8181:8181 -p 6653:6653 onosproject/onos:latest
```

- REST API: `http://localhost:8181/onos/v1/`
- Web UI: `http://localhost:8181/onos/ui`
- 인증: ID `onos` / PW `rocks`
- 시작 후 2~3분 대기 후 접근

### 재시작 시
```bash
docker start onos       # 기존 컨테이너 재시작
docker restart onos     # 재시작
docker logs onos        # 로그 확인
```

---

## 4. ONOS Web UI 활용

### 토폴로지 뷰 단축키
| 키 | 기능 |
|---|---|
| `H` | 호스트 표시/숨김 |
| `L` | 스위치 레이블 토글 (끝 자리: s1=1, s2=2, s3=3, s4=4) |
| `A` | 트래픽 모니터링 (Flow Stats bytes 추천) |
| `0` | 트래픽 모니터링 종료 |
| `R` | 화면 초기화 |

### 트래픽 모니터링
- `A` → **Flow Stats (bytes)** 선택
- Mininet 실험 실행 중에만 링크 위 트래픽 표시
- 호스트 2개 Shift+클릭 → 해당 경로만 하이라이트

### 추천 실험 관찰 순서
1. `H` → 호스트 표시
2. `L` 두 번 → 스위치 ID 표시
3. `A` → Flow Stats (bytes) ON
4. `sudo python3 experiment.py` 실행
5. DROP 룰 배포 전/후 h1↔h4 트래픽 변화 스크린샷

---

## 5. 실시간 시각화 (visualize.py)

ONOS REST API를 3초마다 조회하여 브라우저에서 토폴로지와 FlowRule 상태 표시.

### 실행 (WSL 터미널)
```bash
cd /mnt/c/Users/seonl/Desktop/c/2026/summer/xai/experiments/3_digital_twin
python3 visualize.py
```

### 접근
Windows 브라우저: `http://localhost:7777`

### 기능
- vis.js 인터랙티브 그래프 (다크 테마)
- 스위치 클릭 → FlowRule 상세 (Priority / State / Match→Action)
- 링크 상태 실시간 반영:
  - ACTIVE: 빨강(1 Mbps) / 초록(10 Mbps)
  - INACTIVE: 회색 점선
- 호스트-스위치 연결도 ONOS hosts API로 실시간 반영

---

## 6. 실험 실행

```bash
cd ~/exp3_integrated
sudo python3 experiment.py
```

### 성공 기준 (5/5 PASS)
| 체크 | 내용 |
|---|---|
| `four_switches_discovered` | s1~s4 ONOS 등록 |
| `baseline_h1_to_h4` | DROP 룰 배포 전 h1→h4 ping 성공 |
| `target_h1_to_h4_blocked` | DROP 룰 배포 후 h1→h4 차단 |
| `unrelated_h2_to_h3_reachable` | h2→h3 트래픽 영향 없음 |
| `h1_to_h4_recovered` | DROP 룰 삭제 후 h1→h4 복구 |
