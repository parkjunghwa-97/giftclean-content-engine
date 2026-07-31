"""최종 승인 게이트 — 사람이 승인하지 않으면 렌더링 자체가 진행되지 않는다.

완전 무인 게시/발행 기능은 이 레포에 존재하지 않는다. 이 모듈이 그 원칙을
코드 레벨에서 강제하는 지점이며, 우회 경로를 만들지 않는다.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import masking_check
from onsite_project import ordered_script_segments, project_dir, sorted_manifest


def _approval_path(project_id: str) -> str:
    return os.path.join(project_dir(project_id), "approval.json")


def load_approval(project_id: str) -> dict:
    path = _approval_path(project_id)
    if not os.path.exists(path):
        return {"approved": False, "approved_by": "", "approved_at": None, "notes": ""}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def check_ready(project_id: str) -> list:
    """승인 가능 여부를 확인하고, 해결해야 할 문제 목록을 반환한다 (없으면 빈 리스트)."""
    problems = []
    manifest = sorted_manifest(project_id)
    if not manifest:
        problems.append("등록된 사진이 없습니다.")
        return problems

    try:
        ordered_script_segments(project_id)
    except Exception as e:
        problems.append(f"대본 확인 필요: {e}")

    masking_check.sync_with_manifest(project_id)
    if not masking_check.all_passed(project_id):
        problems.append("개인정보(얼굴/주소/명패/우편물) 마스킹 체크가 모든 사진에서 완료되지 않았습니다.")

    return problems


def approve(project_id: str, approved_by: str, notes: str = "") -> dict:
    if not approved_by or not approved_by.strip():
        raise ValueError("승인자 이름을 입력해야 합니다.")

    problems = check_ready(project_id)
    if problems:
        raise RuntimeError("아직 승인할 수 없습니다:\n- " + "\n- ".join(problems))

    record = {
        "approved": True,
        "approved_by": approved_by.strip(),
        "approved_at": datetime.now(timezone.utc).isoformat(),
        "notes": notes,
    }
    with open(_approval_path(project_id), "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    return record


def revoke(project_id: str):
    record = {"approved": False, "approved_by": "", "approved_at": None, "notes": ""}
    with open(_approval_path(project_id), "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    return record


def enforce_or_raise(project_id: str):
    """렌더링 직전 호출. 승인 조건을 만족하지 않으면 예외를 던져 렌더링을 차단한다."""
    approval = load_approval(project_id)
    problems = check_ready(project_id)
    if not approval.get("approved"):
        problems.append("최종 승인이 완료되지 않았습니다 (검수 화면에서 승인 버튼을 눌러주세요).")
    if problems:
        raise PermissionError(
            "렌더링이 차단되었습니다. 다음을 먼저 해결하세요:\n- " + "\n- ".join(problems)
        )
