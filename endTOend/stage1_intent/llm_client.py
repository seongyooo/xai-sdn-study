"""
stage1_intent/llm_client.py — LLM/임베딩 백엔드 추상화

두 가지 백엔드를 지원한다:
  - Ollama (기본): OpenAI-compatible REST API + SSE 스트리밍
  - Gemini: google-genai SDK

두 백엔드 모두 JSON 응답 반환 및 텍스트 임베딩을 지원한다.
재시도: 3회, 지수 백오프.
"""
from __future__ import annotations

import json
import time
from typing import Optional

import config


class LLMClient:
    """LLM 추론 및 임베딩 클라이언트 (Ollama / Gemini 추상화)"""

    def __init__(self, model: Optional[str] = None) -> None:
        self.model = model or config.LLM_MODEL
        self.base_url = config.LLM_BASE_URL.rstrip("/")
        self.api_key = config.LLM_API_KEY
        self.embed_model = config.EMBED_MODEL

    # ── 공개 인터페이스 ────────────────────────────────────────

    def call(self, system: str, user: str) -> dict | None:
        """
        LLM에 system + user 메시지를 보내고 JSON 응답을 반환한다.
        실패 시 None 반환.
        """
        if self._is_gemini():
            return self._gemini_call(system, user)
        return self._ollama_call(system, user)

    def embed(self, text: str) -> list[float]:
        """
        텍스트 임베딩 벡터 반환.
        """
        if self._is_gemini():
            return self._gemini_embed(text)
        return self._ollama_embed(text)

    def _is_gemini(self) -> bool:
        return config.is_gemini(self.model)

    # ── Ollama 백엔드 ─────────────────────────────────────────

    def _ollama_call(self, system: str, user: str) -> dict | None:
        """Ollama OpenAI-compatible API로 LLM 호출 (SSE 스트리밍)"""
        import urllib.request
        import urllib.error

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": True,
            "temperature": 0.2,
        }

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        for attempt in range(3):
            try:
                data = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(url, data=data, headers=headers, method="POST")

                with urllib.request.urlopen(req, timeout=120) as resp:
                    # SSE 스트리밍 파싱
                    full_content = ""
                    for raw_line in resp:
                        line = raw_line.decode("utf-8").strip()
                        if not line:
                            continue
                        if line.startswith("data:"):
                            chunk = line[5:].strip()
                            if chunk == "[DONE]":
                                break
                            try:
                                chunk_json = json.loads(chunk)
                                delta = (
                                    chunk_json.get("choices", [{}])[0]
                                    .get("delta", {})
                                    .get("content", "")
                                )
                                if delta:
                                    full_content += delta
                            except json.JSONDecodeError:
                                continue

                # JSON 파싱 시도
                full_content = full_content.strip()
                # ```json ... ``` 코드 블록 제거
                if full_content.startswith("```"):
                    lines = full_content.split("\n")
                    # 첫 줄(```json)과 마지막 줄(```) 제거
                    inner = lines[1:] if lines[0].startswith("```") else lines
                    if inner and inner[-1].strip() == "```":
                        inner = inner[:-1]
                    full_content = "\n".join(inner)
                # <think>...</think> 블록 제거 (qwen3 thinking mode)
                if "<think>" in full_content:
                    import re
                    full_content = re.sub(r"<think>.*?</think>", "", full_content, flags=re.DOTALL).strip()

                return json.loads(full_content)

            except (urllib.error.URLError, urllib.error.HTTPError) as exc:
                wait = 2 ** attempt
                print(f"  [LLM 재시도 {attempt+1}/3] 네트워크 오류: {str(exc)[:60]} — {wait}s 대기")
                time.sleep(wait)
            except json.JSONDecodeError as exc:
                wait = 2 ** attempt
                print(f"  [LLM 재시도 {attempt+1}/3] JSON 파싱 실패: {str(exc)[:60]} — {wait}s 대기")
                time.sleep(wait)

        return None

    def _ollama_embed(self, text: str) -> list[float]:
        """Ollama /embeddings 엔드포인트로 텍스트 임베딩"""
        import urllib.request
        import urllib.error

        payload = {
            "model": self.embed_model,
            "input": text,
        }
        url = f"{self.base_url}/embeddings"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        for attempt in range(3):
            try:
                data = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(url, data=data, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=60) as resp:
                    result = json.loads(resp.read().decode("utf-8"))
                    # OpenAI 형식: data[0].embedding
                    emb_data = result.get("data", [])
                    if emb_data:
                        return emb_data[0].get("embedding", [])
                    # 대안 형식: embedding 직접
                    return result.get("embedding", [])
            except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
                wait = 2 ** attempt
                print(f"  [임베딩 재시도 {attempt+1}/3] {str(exc)[:60]} — {wait}s 대기")
                time.sleep(wait)

        raise RuntimeError(f"임베딩 실패 (모델={self.embed_model}, 재시도 3회 초과)")

    # ── Gemini 백엔드 ─────────────────────────────────────────

    def _gemini_call(self, system: str, user: str) -> dict | None:
        """Google Gemini API로 LLM 호출 (JSON 응답)"""
        from google import genai
        from google.genai import types

        api_key = config.GOOGLE_API_KEY
        if not api_key:
            raise RuntimeError("GOOGLE_API_KEY가 설정되지 않았습니다.")

        client = genai.Client(api_key=api_key)

        for attempt in range(4):
            try:
                response = client.models.generate_content(
                    model=self.model,
                    contents=user,
                    config=types.GenerateContentConfig(
                        system_instruction=system,
                        response_mime_type="application/json",
                        temperature=0.2,
                    ),
                )
                return json.loads(response.text)
            except Exception as exc:
                err_str = str(exc)
                # 429 Rate Limit: 더 긴 대기
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    wait = [30, 60, 120, 180][attempt]
                else:
                    wait = 2 ** attempt
                print(f"  [Gemini 재시도 {attempt+1}/4] {err_str[:80]} — {wait}s 대기")
                time.sleep(wait)

        return None

    def _gemini_embed(self, text: str) -> list[float]:
        """Google Gemini 임베딩 (gemini-embedding-001)"""
        from google import genai

        api_key = config.GOOGLE_API_KEY
        if not api_key:
            raise RuntimeError("GOOGLE_API_KEY가 설정되지 않았습니다.")

        client = genai.Client(api_key=api_key)

        for attempt in range(3):
            try:
                result = client.models.embed_content(
                    model="gemini-embedding-001",
                    contents=text,
                )
                return result.embeddings[0].values
            except Exception as exc:
                wait = 2 ** attempt
                print(f"  [Gemini 임베딩 재시도 {attempt+1}/3] {str(exc)[:60]} — {wait}s 대기")
                time.sleep(wait)

        raise RuntimeError("Gemini 임베딩 실패 (재시도 3회 초과)")
