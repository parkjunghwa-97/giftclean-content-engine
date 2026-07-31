"""대본 문단과 실제 TTS 길이를 이용해 세그먼트별 SRT 자막을 생성합니다."""
from __future__ import annotations

import re

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def _split_sentences(text: str):
    parts = [p.strip() for p in _SENTENCE_SPLIT_RE.split(text) if p.strip()]
    return parts or [text]


def _format_ts(seconds: float) -> str:
    ms_total = max(int(round(seconds * 1000)), 0)
    h, ms_total = divmod(ms_total, 3600000)
    m, ms_total = divmod(ms_total, 60000)
    s, ms = divmod(ms_total, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def generate_segment_srt(text: str, duration: float, out_path: str) -> str:
    """세그먼트(사진 1장 분량) 대본 텍스트를 실제 나레이션 길이에 맞춰 SRT로 만든다."""
    sentences = _split_sentences(text)
    total_chars = sum(len(s) for s in sentences) or 1

    lines = []
    cursor = 0.0
    idx = 1
    for sentence in sentences:
        share = len(sentence) / total_chars
        seg_dur = max(duration * share, 0.8)
        start = cursor
        end = min(cursor + seg_dur, duration)
        lines.append(str(idx))
        lines.append(f"{_format_ts(start)} --> {_format_ts(end)}")
        lines.append(sentence)
        lines.append("")
        idx += 1
        cursor = end

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return out_path
