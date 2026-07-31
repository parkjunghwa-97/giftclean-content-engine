"""현장형(Before/작업중/After 사진) 프로젝트 관리.

사진 업로드·순서 지정과 그 순서에 맞춘 대본(script.txt) 템플릿 생성/파싱을
담당한다. 대본은 AI가 만들지 않는다 — 사용자가 실제 현장을 보고 직접
작성한 내용을 그대로 사용한다 (SOP: 실제 현장정보 기반 원칙).
"""
from __future__ import annotations

import json
import os
import re
import shutil

PROJECTS_ROOT = "projects"
VALID_PHASES = ("before", "during", "after")
PHASE_LABELS = {"before": "작업 전(Before)", "during": "작업 중", "after": "작업 후(After)"}
PLACEHOLDER_TEXT = "(이 사진에 대한 실제 현장 설명을 여기에 작성하세요)"

SEGMENT_HEADER_RE = re.compile(r"^#\s*\[(\d+)\]\s*(\S+)\s*-\s*(.+)$")


def project_dir(project_id: str) -> str:
    path = os.path.join(PROJECTS_ROOT, project_id)
    os.makedirs(path, exist_ok=True)
    return path


def _manifest_path(project_id: str) -> str:
    return os.path.join(project_dir(project_id), "manifest.json")


def _script_path(project_id: str) -> str:
    return os.path.join(project_dir(project_id), "script.txt")


def script_path(project_id: str) -> str:
    return _script_path(project_id)


def load_manifest(project_id: str) -> list:
    path = _manifest_path(project_id)
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_manifest(project_id: str, items: list):
    with open(_manifest_path(project_id), "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def sorted_manifest(project_id: str) -> list:
    return sorted(load_manifest(project_id), key=lambda i: i["order"])


def import_photos(project_id: str, photos: list) -> list:
    """photos: [(원본경로, phase), ...] — 리스트 순서가 곧 최종 사진 순서.
    phase는 'before' | 'during' | 'after' 중 하나여야 한다.
    """
    photos_dir = os.path.join(project_dir(project_id), "photos")
    os.makedirs(photos_dir, exist_ok=True)

    items = []
    for idx, (src_path, phase) in enumerate(photos):
        if phase not in VALID_PHASES:
            raise ValueError(f"잘못된 phase '{phase}' (허용값: {VALID_PHASES})")
        if not os.path.exists(src_path):
            raise FileNotFoundError(f"사진을 찾을 수 없습니다: {src_path}")
        ext = os.path.splitext(src_path)[1].lower() or ".jpg"
        filename = f"{idx:02d}_{phase}{ext}"
        dest_path = os.path.join(photos_dir, filename)
        shutil.copy(src_path, dest_path)
        items.append({
            "filename": filename,
            "path": dest_path,
            "phase": phase,
            "order": idx,
            "original_name": os.path.basename(src_path),
        })

    _save_manifest(project_id, items)
    if not os.path.exists(_script_path(project_id)):
        _write_script_template(project_id, items)
    else:
        _resync_script_template(project_id, items)
    return items


def reorder_photos(project_id: str, ordered_filenames: list) -> list:
    """이미 등록된 사진들을 지정한 순서(파일명 리스트)로 재배열한다."""
    items = load_manifest(project_id)
    by_name = {item["filename"]: item for item in items}

    missing = [name for name in ordered_filenames if name not in by_name]
    if missing:
        raise ValueError(f"매니페스트에 없는 파일명입니다: {missing}")
    if set(ordered_filenames) != set(by_name.keys()):
        raise ValueError("순서 목록에 모든 사진이 정확히 한 번씩 포함되어야 합니다.")

    reordered = []
    for idx, name in enumerate(ordered_filenames):
        item = by_name[name]
        item["order"] = idx
        reordered.append(item)

    _save_manifest(project_id, reordered)
    _resync_script_template(project_id, reordered)
    return reordered


def _segment_marker(order: int, phase: str, filename: str) -> str:
    return f"# [{order + 1}] {phase} - {filename}"


def _render_template(items: list, texts_by_filename: dict) -> str:
    lines = [
        "# 현장형 숏폼 대본",
        "# 아래 각 [번호] 사진 항목 아래 줄에 실제 현장 내용을 바탕으로 대본을 작성하세요.",
        "# '#'으로 시작하는 줄은 주석이며 대본에 포함되지 않습니다.",
        "# 사진 순서를 바꾸면(reorder) 이 파일도 자동으로 재정렬됩니다.",
        "",
    ]
    for item in sorted(items, key=lambda i: i["order"]):
        lines.append(_segment_marker(item["order"], item["phase"], item["filename"]))
        lines.append(texts_by_filename.get(item["filename"], PLACEHOLDER_TEXT))
        lines.append("")
    return "\n".join(lines)


def _write_script_template(project_id: str, items: list):
    content = _render_template(items, {})
    with open(_script_path(project_id), "w", encoding="utf-8") as f:
        f.write(content)


def _resync_script_template(project_id: str, items: list):
    """사진 순서가 바뀌어도 파일명 기준으로 기존에 작성한 문단을 그대로 유지한다."""
    existing = parse_script(project_id, strict=False)
    content = _render_template(items, existing)
    with open(_script_path(project_id), "w", encoding="utf-8") as f:
        f.write(content)


def parse_script(project_id: str, expected_filenames: list = None, strict: bool = True) -> dict:
    """script.txt를 파싱해 {filename: 대본텍스트} 딕셔너리로 반환한다."""
    path = _script_path(project_id)
    if not os.path.exists(path):
        if strict:
            raise FileNotFoundError("script.txt가 없습니다. 먼저 사진을 등록하세요 (init).")
        return {}

    with open(path, "r", encoding="utf-8") as f:
        raw_lines = f.read().splitlines()

    segments = {}
    current_filename = None
    buffer = []

    def flush():
        if current_filename is not None:
            segments[current_filename] = "\n".join(buffer).strip()

    for line in raw_lines:
        stripped = line.strip()
        m = SEGMENT_HEADER_RE.match(stripped)
        if m:
            flush()
            current_filename = m.group(3).strip()
            buffer = []
        elif stripped.startswith("#"):
            continue
        else:
            if current_filename is not None:
                buffer.append(line)
    flush()

    if strict:
        unwritten = [fn for fn, text in segments.items() if not text or text == PLACEHOLDER_TEXT]
        if unwritten:
            raise ValueError(
                f"아직 작성되지 않은 대본이 있습니다: {unwritten}. "
                f"{path} 파일을 열어 내용을 채운 뒤 다시 시도하세요."
            )
        if expected_filenames is not None:
            missing = [fn for fn in expected_filenames if fn not in segments]
            if missing:
                raise ValueError(f"대본에서 누락된 사진 항목: {missing}")

    return segments


def ordered_script_segments(project_id: str) -> list:
    """사진 순서에 맞춘 [{filename, phase, path, text}, ...] 리스트를 반환한다."""
    items = sorted_manifest(project_id)
    if not items:
        raise ValueError("등록된 사진이 없습니다. 먼저 사진을 등록하세요 (init).")
    filenames = [i["filename"] for i in items]
    segments = parse_script(project_id, expected_filenames=filenames, strict=True)
    return [
        {"filename": i["filename"], "phase": i["phase"], "path": i["path"], "text": segments[i["filename"]]}
        for i in items
    ]
