"""
stage1_intent/rag.py — RAG (Retrieval-Augmented Generation) 인덱스 구축 및 검색

CSV 데이터셋에서 instruction 필드를 임베딩하여 FAISS 인덱스를 구축하고,
쿼리 인텐트와 유사한 예시를 검색한다.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from stage1_intent.llm_client import LLMClient


def build_index(
    dataset_path: Path,
    client: "LLMClient",
) -> tuple:
    """
    CSV 데이터셋에서 instruction 임베딩 → FAISS 인덱스 구축.

    Args:
        dataset_path: intent CSV 파일 경로 (instruction, output 컬럼 필수)
        client: LLMClient 인스턴스

    Returns:
        (faiss_index, texts, outputs)
        - faiss_index: faiss.IndexFlatL2 객체
        - texts: instruction 문자열 리스트
        - outputs: 대응하는 output 문자열 리스트
    """
    try:
        import faiss
        import numpy as np
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError(
            "RAG 의존성이 설치되지 않았습니다: pip install faiss-cpu numpy pandas"
        ) from exc

    df = pd.read_csv(dataset_path)

    # 컬럼 존재 확인
    if "instruction" not in df.columns or "output" not in df.columns:
        raise ValueError(
            f"CSV에 'instruction', 'output' 컬럼이 필요합니다. "
            f"현재 컬럼: {list(df.columns)}"
        )

    texts: list[str] = df["instruction"].astype(str).tolist()
    outputs: list[str] = df["output"].astype(str).tolist()

    print(f"  RAG 인덱스 구축 중 ({len(texts)}개 예시)...")

    embeddings = []
    for i, text in enumerate(texts):
        if (i + 1) % 10 == 0 or i == 0:
            print(f"    임베딩 {i+1}/{len(texts)}...", end="\r")
        emb = client.embed(text)
        embeddings.append(emb)

    print(f"\n    임베딩 완료 ({len(embeddings)}개)")

    emb_matrix = np.array(embeddings, dtype="float32")
    dim = emb_matrix.shape[1]

    index = faiss.IndexFlatL2(dim)
    index.add(emb_matrix)

    return index, texts, outputs


def search_similar(
    query: str,
    index,
    texts: list[str],
    outputs: list[str],
    client: "LLMClient",
    k: int = 3,
) -> list[tuple[str, str]]:
    """
    쿼리와 유사한 예시 k개 검색.

    Args:
        query: 검색할 인텐트 문자열
        index: faiss.IndexFlatL2 객체
        texts: instruction 리스트
        outputs: output 리스트
        client: LLMClient 인스턴스
        k: 검색할 예시 수

    Returns:
        [(instruction, output), ...] 유사도 내림차순
    """
    import numpy as np

    q_emb = np.array([client.embed(query)], dtype="float32")
    distances, indices = index.search(q_emb, k)

    results = []
    for idx in indices[0]:
        if 0 <= idx < len(texts):
            results.append((texts[idx], outputs[idx]))

    return results
