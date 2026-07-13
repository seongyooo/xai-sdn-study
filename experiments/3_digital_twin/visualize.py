"""
실험 3 Digital Twin 실시간 시각화 도구

ONOS REST API를 주기적으로 조회하여 브라우저에서 실시간으로
네트워크 토폴로지와 FlowRule 상태를 보여준다.

실행: python visualize.py
      → 브라우저가 자동으로 열리고 3초마다 자동 갱신됨
"""

import json
import time
import webbrowser
import threading
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.request import Request, urlopen
import base64

REFRESH_INTERVAL = 3  # 초

ONOS_BASE = "http://127.0.0.1:8181/onos/v1"
ONOS_AUTH = base64.b64encode(b"onos:rocks").decode()
OUT_PATH = Path(__file__).parent / "topology_viz.html"

# 다이아몬드 토폴로지 고정 좌표 (시각화용)
NODE_POS = {
    "of:0000000000000001": (300, 400),
    "of:0000000000000002": (600, 200),
    "of:0000000000000003": (600, 600),
    "of:0000000000000004": (900, 400),
    "h1": (50,  300),
    "h2": (50,  500),
    "h3": (1150, 300),
    "h4": (1150, 500),
}
NODE_LABELS = {
    "of:0000000000000001": "s1",
    "of:0000000000000002": "s2",
    "of:0000000000000003": "s3",
    "of:0000000000000004": "s4",
}


def onos_get(path):
    req = Request(
        f"{ONOS_BASE}/{path}",
        headers={"Authorization": f"Basic {ONOS_AUTH}", "Accept": "application/json"},
    )
    try:
        with urlopen(req, timeout=5) as r:
            return json.loads(r.read())
    except Exception:
        return {}


def fetch_state():
    devices = onos_get("devices").get("devices", [])
    links   = onos_get("links").get("links", [])
    hosts   = onos_get("hosts").get("hosts", [])
    flows   = onos_get("flows").get("flows", [])
    return devices, links, hosts, flows


def flow_summary(flow):
    criteria = flow.get("selector", {}).get("criteria", [])
    instructions = flow.get("treatment", {}).get("instructions", [])
    match_parts = []
    for c in criteria:
        t = c.get("type", "")
        if t == "ETH_TYPE":   match_parts.append(f"eth={c.get('ethType')}")
        elif t == "IPV4_SRC": match_parts.append(f"src={c.get('ip')}")
        elif t == "IPV4_DST": match_parts.append(f"dst={c.get('ip')}")
        elif t == "IP_PROTO": match_parts.append(f"proto={c.get('protocol')}")
        elif t == "TCP_DST":  match_parts.append(f"tcp_dst={c.get('tcpPort')}")
    action = "DROP" if not instructions else ",".join(
        f"{i.get('type')}:{i.get('port','')}" for i in instructions
    )
    return f"[{','.join(match_parts)}] → {action}"


def build_html(devices, links, hosts, flows):
    # 디바이스별 flow 그룹
    flows_by_device = {}
    for f in flows:
        did = f.get("deviceId", "")
        flows_by_device.setdefault(did, []).append(f)

    # vis.js 노드 데이터
    vis_nodes = []
    vis_edges = []

    for did, (x, y) in NODE_POS.items():
        if did.startswith("of:"):
            label = NODE_LABELS.get(did, did[-4:])
            fcount = len(flows_by_device.get(did, []))
            vis_nodes.append({
                "id": did,
                "label": f"{label}\\nflows: {fcount}",
                "x": x - 400, "y": y - 300,
                "shape": "box",
                "color": {"background": "#1a6496", "border": "#5bc0de",
                          "highlight": {"background": "#2980b9", "border": "#5bc0de"}},
                "font": {"color": "#ecf0f1", "size": 13, "bold": True},
                "borderWidth": 2,
                "shadow": True,
                "group": "switch",
                "title": did,
            })
        else:
            vis_nodes.append({
                "id": did,
                "label": did,
                "x": x - 400, "y": y - 300,
                "shape": "ellipse",
                "color": {"background": "#27ae60", "border": "#2ecc71",
                          "highlight": {"background": "#2ecc71", "border": "#27ae60"}},
                "font": {"color": "#ecf0f1", "size": 12},
                "borderWidth": 2,
                "shadow": True,
                "group": "host",
            })

    # ONOS에서 받은 실제 링크 상태로 active 여부 판단
    active_pairs = set()
    for lnk in links:
        src_dev = lnk.get("src", {}).get("device", "")
        dst_dev = lnk.get("dst", {}).get("device", "")
        if lnk.get("state", "") == "ACTIVE":
            active_pairs.add((src_dev, dst_dev))
            active_pairs.add((dst_dev, src_dev))

    # ONOS hosts에서 호스트-스위치 연결 active 여부 판단
    host_location = {}  # host_id → switch_did
    for h in hosts:
        hid = h.get("id", "")
        # ip 기준으로 h1~h4 매핑
        for ip_info in h.get("ipAddresses", []):
            ip = ip_info if isinstance(ip_info, str) else ""
            loc = h.get("locations", [{}])[0] if h.get("locations") else {}
            switch = loc.get("elementId", "")
            if ip == "10.0.0.1": host_location["h1"] = switch
            elif ip == "10.0.0.2": host_location["h2"] = switch
            elif ip == "10.0.0.3": host_location["h3"] = switch
            elif ip == "10.0.0.4": host_location["h4"] = switch

    # 토폴로지 링크 정의 (src, dst, bandwidth, active_color)
    fixed_links = [
        ("of:0000000000000001", "of:0000000000000002", "1 Mbps",  "#e74c3c"),
        ("of:0000000000000002", "of:0000000000000004", "1 Mbps",  "#e74c3c"),
        ("of:0000000000000001", "of:0000000000000003", "10 Mbps", "#2ecc71"),
        ("of:0000000000000003", "of:0000000000000004", "10 Mbps", "#2ecc71"),
        ("h1", "of:0000000000000001", "", "#7f8c8d"),
        ("h2", "of:0000000000000001", "", "#7f8c8d"),
        ("h3", "of:0000000000000004", "", "#7f8c8d"),
        ("h4", "of:0000000000000004", "", "#7f8c8d"),
    ]
    for i, (src, dst, bw, active_color) in enumerate(fixed_links):
        # 스위치-스위치 링크: ONOS link 상태 반영
        if src.startswith("of:") and dst.startswith("of:"):
            is_active = (src, dst) in active_pairs
        # 호스트-스위치 링크: hosts API 반영
        else:
            host_id = src if not src.startswith("of:") else dst
            expected_sw = dst if not src.startswith("of:") else src
            is_active = host_location.get(host_id) == expected_sw

        if is_active:
            color = active_color
            dash = False
            width = 3 if bw else 2
        else:
            color = "#2d3748"
            dash = True
            width = 1

        edge = {
            "id": i,
            "from": src,
            "to": dst,
            "color": {"color": color, "highlight": "#f39c12"},
            "width": width,
            "smooth": {"type": "continuous"},
            "dashes": dash,
        }
        if bw:
            edge["label"] = bw if is_active else ""
            edge["font"] = {"color": color, "size": 11, "align": "middle",
                            "background": "#1a1a2e"}
        vis_edges.append(edge)

    # flow 패널 데이터 (JS용)
    flows_js = {}
    for did, flist in flows_by_device.items():
        label = NODE_LABELS.get(did, did)
        rows = ""
        for f in sorted(flist, key=lambda x: -x.get("priority", 0)):
            pri = f.get("priority", 0)
            state = f.get("state", "")
            summary = flow_summary(f)
            if pri >= 40000:
                row_class = "flow-high"
            elif pri > 10:
                row_class = "flow-mid"
            else:
                row_class = "flow-low"
            state_badge = (
                f'<span class="badge badge-added">ADDED</span>' if state == "ADDED"
                else f'<span class="badge badge-pending">PENDING</span>' if "PENDING" in state
                else f'<span class="badge badge-other">{state}</span>'
            )
            rows += f'<tr class="{row_class}"><td>{pri}</td><td>{state_badge}</td><td class="mono">{summary}</td></tr>'
        flows_js[did] = {
            "label": label,
            "did": did,
            "rows": rows if rows else "",
        }

    flows_js_str = json.dumps(flows_js)
    nodes_json = json.dumps(vis_nodes)
    edges_json = json.dumps(vis_edges)
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    total_flows = len(flows)
    num_devices = len(devices)
    num_hosts = len(hosts)
    refresh_ms = REFRESH_INTERVAL * 1000

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>Digital Twin — ONOS Topology Viewer</title>
<script src="https://unpkg.com/vis-network@9.1.9/dist/vis-network.min.js"></script>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #0d1117; color: #c9d1d9; height: 100vh; display: flex; flex-direction: column; }}

  /* ── Header ── */
  header {{ background: #161b22; border-bottom: 1px solid #30363d; padding: 0 20px; height: 52px; display: flex; align-items: center; justify-content: space-between; flex-shrink: 0; }}
  .logo {{ display: flex; align-items: center; gap: 10px; }}
  .logo-icon {{ width: 28px; height: 28px; background: linear-gradient(135deg, #1a6496, #2980b9); border-radius: 6px; display: flex; align-items: center; justify-content: center; font-size: 16px; }}
  .logo h1 {{ font-size: 16px; font-weight: 600; color: #e6edf3; letter-spacing: 0.3px; }}
  .header-right {{ display: flex; align-items: center; gap: 12px; }}
  .stat-pill {{ background: #21262d; border: 1px solid #30363d; border-radius: 20px; padding: 4px 12px; font-size: 12px; color: #8b949e; }}
  .stat-pill span {{ color: #58a6ff; font-weight: 600; }}
  .refresh-badge {{ background: #1f6feb22; border: 1px solid #1f6feb; color: #58a6ff; border-radius: 4px; padding: 3px 8px; font-size: 11px; }}

  /* ── Layout ── */
  .main {{ display: flex; flex: 1; overflow: hidden; min-height: 0; }}
  #topology {{ flex: 1; background: #0d1117; width: 100%; height: 100%; }}

  /* ── Side Panel ── */
  .panel {{ width: 440px; background: #161b22; border-left: 1px solid #30363d; display: flex; flex-direction: column; overflow: hidden; }}
  .panel-header {{ padding: 14px 16px; border-bottom: 1px solid #30363d; background: #161b22; }}
  .panel-header h2 {{ font-size: 14px; font-weight: 600; color: #e6edf3; }}
  .panel-header .sub {{ font-size: 11px; color: #8b949e; margin-top: 3px; }}
  .panel-body {{ flex: 1; overflow-y: auto; padding: 16px; }}
  .panel-body::-webkit-scrollbar {{ width: 6px; }}
  .panel-body::-webkit-scrollbar-track {{ background: #161b22; }}
  .panel-body::-webkit-scrollbar-thumb {{ background: #30363d; border-radius: 3px; }}

  /* ── Empty state ── */
  .empty-state {{ text-align: center; padding: 60px 20px; color: #8b949e; }}
  .empty-state .icon {{ font-size: 40px; margin-bottom: 12px; }}
  .empty-state p {{ font-size: 13px; line-height: 1.6; }}

  /* ── Device info card ── */
  .device-card {{ background: #21262d; border: 1px solid #30363d; border-radius: 8px; padding: 12px 14px; margin-bottom: 14px; }}
  .device-card .did {{ font-size: 10px; color: #8b949e; font-family: monospace; margin-top: 4px; word-break: break-all; }}
  .device-title {{ font-size: 15px; font-weight: 700; color: #58a6ff; }}

  /* ── Flow table ── */
  .flow-table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
  .flow-table th {{ background: #21262d; color: #8b949e; padding: 7px 10px; text-align: left; font-weight: 600; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; border-bottom: 1px solid #30363d; }}
  .flow-table td {{ padding: 7px 10px; border-bottom: 1px solid #21262d; vertical-align: top; }}
  .flow-table tr:last-child td {{ border-bottom: none; }}
  .flow-high td {{ background: #3d1f00; }}
  .flow-mid td {{ background: #0d2a0d; }}
  .flow-low td {{ background: #0d1117; }}
  .flow-high:hover td, .flow-mid:hover td, .flow-low:hover td {{ filter: brightness(1.3); }}
  .mono {{ font-family: 'Courier New', monospace; font-size: 11px; color: #a5d6ff; word-break: break-all; }}
  .no-flows {{ text-align: center; padding: 20px; color: #8b949e; font-size: 12px; }}

  /* ── Badges ── */
  .badge {{ display: inline-block; border-radius: 3px; padding: 1px 6px; font-size: 10px; font-weight: 700; }}
  .badge-added {{ background: #1f6feb33; color: #58a6ff; border: 1px solid #1f6feb55; }}
  .badge-pending {{ background: #b5720022; color: #e3b341; border: 1px solid #b5720044; }}
  .badge-other {{ background: #30363d; color: #8b949e; border: 1px solid #444; }}

  /* ── Legend ── */
  .legend {{ position: absolute; bottom: 16px; left: 16px; background: #161b22cc; border: 1px solid #30363d; border-radius: 8px; padding: 10px 14px; backdrop-filter: blur(4px); }}
  .legend-row {{ display: flex; align-items: center; gap: 8px; font-size: 11px; color: #8b949e; margin-bottom: 5px; }}
  .legend-row:last-child {{ margin-bottom: 0; }}
  .legend-dot {{ width: 10px; height: 10px; border-radius: 2px; }}
  .legend-line {{ width: 20px; height: 3px; border-radius: 2px; }}
</style>
</head>
<body>
<header>
  <div class="logo">
    <div class="logo-icon">&#128301;</div>
    <h1>Digital Twin &mdash; ONOS Topology Viewer</h1>
  </div>
  <div class="header-right">
    <div class="stat-pill">Switches <span>{num_devices}</span></div>
    <div class="stat-pill">Hosts <span>{num_hosts}</span></div>
    <div class="stat-pill">FlowRules <span>{total_flows}</span></div>
    <div class="stat-pill">Updated <span>{now}</span></div>
    <div class="refresh-badge">&#8635; {REFRESH_INTERVAL}s</div>
  </div>
</header>
<div class="main">
  <div style="position:relative;flex:1;">
    <div id="topology"></div>
    <div class="legend">
      <div class="legend-row"><div class="legend-dot" style="background:#1a6496;border:1px solid #5bc0de"></div> Switch (click for flows)</div>
      <div class="legend-row"><div class="legend-dot" style="background:#27ae60;border-radius:50%"></div> Host</div>
      <div class="legend-row"><div class="legend-line" style="background:#e74c3c"></div> 1 Mbps (active)</div>
      <div class="legend-row"><div class="legend-line" style="background:#2ecc71"></div> 10 Mbps (active)</div>
      <div class="legend-row"><div class="legend-line" style="background:#2d3748;border-top:1px dashed #555"></div> inactive</div>
    </div>
  </div>
  <div class="panel">
    <div class="panel-header">
      <h2>FlowRule Details</h2>
      <div class="sub" id="panel-sub">Click a switch to view its flow rules</div>
    </div>
    <div class="panel-body" id="flow-detail">
      <div class="empty-state">
        <div class="icon">&#128257;</div>
        <p>Select a switch node in the topology<br>to inspect its installed FlowRules.</p>
      </div>
    </div>
  </div>
</div>
<script>
const flowsData = {flows_js_str};
const nodesData = {nodes_json};
const edgesData = {edges_json};

const container = document.getElementById('topology');
const network = new vis.Network(container,
  {{ nodes: new vis.DataSet(nodesData), edges: new vis.DataSet(edgesData) }},
  {{
    physics: false,
    interaction: {{ hover: true, tooltipDelay: 200, zoomView: true, dragView: true }},
    nodes: {{ fixed: true }},
    edges: {{ arrows: {{ to: false }} }},
  }}
);
network.once('afterDrawing', function() {{
  network.fit({{ animation: false, padding: 60 }});
}});

function showFlows(deviceId) {{
  const d = flowsData[deviceId];
  if (!d) return;
  document.getElementById('panel-sub').textContent = d.did;
  const rows = d.rows
    ? `<table class="flow-table">
        <thead><tr><th>Priority</th><th>State</th><th>Match &#8594; Action</th></tr></thead>
        <tbody>${{d.rows}}</tbody>
       </table>`
    : '<div class="no-flows">No flows installed on this switch.</div>';
  document.getElementById('flow-detail').innerHTML =
    `<div class="device-card">
      <div class="device-title">${{d.label}}</div>
      <div class="did">${{d.did}}</div>
     </div>` + rows;
  localStorage.setItem('selectedDevice', deviceId);
}}

network.on('click', function(params) {{
  if (params.nodes.length > 0) {{
    const nid = params.nodes[0];
    if (nid.startsWith('of:')) showFlows(nid);
  }}
}});

network.on('hoverNode', function(params) {{
  container.style.cursor = params.node.startsWith('of:') ? 'pointer' : 'default';
}});
network.on('blurNode', function() {{ container.style.cursor = 'default'; }});

window.onload = () => {{
  const saved = localStorage.getItem('selectedDevice');
  if (saved && flowsData[saved]) showFlows(saved);
  setTimeout(() => location.reload(), {refresh_ms});
}};
</script>
</body>
</html>"""


class VisualizationHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        devices, links, hosts, flows = fetch_state()
        if not devices:
            body = "<h2>ONOS connecting...</h2><script>setTimeout(()=>location.reload(),3000)</script>".encode("utf-8")
        else:
            body = build_html(devices, links, hosts, flows).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass  # 요청 로그 숨김


def main():
    port = 7777
    server = HTTPServer(("0.0.0.0", port), VisualizationHandler)
    url = f"http://127.0.0.1:{port}"
    print(f"시각화 서버 시작: {url}")
    print(f"브라우저에서 열기: {url}")
    print(f"자동 갱신: {REFRESH_INTERVAL}초마다  |  종료: Ctrl+C")
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n서버 종료")


if __name__ == "__main__":
    main()
