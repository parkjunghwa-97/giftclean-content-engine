"""개인정보(얼굴/주소/명패/우편물) 노출 여부 체크리스트.

자동 인식은 하지 않는다 — SOP 원칙상 승인 전에 사람이 사진을 직접 보고
확인해야 한다. 승인 게이트(approval.py)는 이 체크리스트가 모든 사진에서
전부 통과되어야만 승인을 허용한다.
"""
from __future__ import annotations

import json
import os

from onsite_project import project_dir, sorted_manifest

CHECK_FIELDS = ["face", "address", "nameplate", "mail"]
FIELD_LABELS = {
    "face": "얼굴",
    "address": "주소",
    "nameplate": "명패",
    "mail": "우편물",
}


def _checklist_path(project_id: str) -> str:
    return os.path.join(project_dir(project_id), "masking_checklist.json")


def load_checklist(project_id: str) -> dict:
    path = _checklist_path(project_id)
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_checklist(project_id: str, data: dict):
    with open(_checklist_path(project_id), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def sync_with_manifest(project_id: str) -> dict:
    """사진 매니페스트 기준으로 체크리스트 항목을 새로 만들거나 정리한다."""
    manifest = sorted_manifest(project_id)
    checklist = load_checklist(project_id)
    filenames = {item["filename"] for item in manifest}

    for name in filenames:
        if name not in checklist:
            checklist[name] = {field: False for field in CHECK_FIELDS}

    for name in list(checklist.keys()):
        if name not in filenames:
            del checklist[name]

    _save_checklist(project_id, checklist)
    return checklist


def update_check(project_id: str, filename: str, **flags) -> dict:
    checklist = load_checklist(project_id)
    if filename not in checklist:
        raise ValueError(f"체크리스트에 없는 사진입니다: {filename}")
    for key, value in flags.items():
        if key in CHECK_FIELDS:
            checklist[filename][key] = bool(value)
    _save_checklist(project_id, checklist)
    return checklist


def all_passed(project_id: str) -> bool:
    checklist = load_checklist(project_id)
    manifest = sorted_manifest(project_id)
    if not manifest:
        return False
    for item in manifest:
        entry = checklist.get(item["filename"])
        if not entry or not all(entry.get(field, False) for field in CHECK_FIELDS):
            return False
    return True
