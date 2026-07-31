"""현장형 숏폼 로컬 검수 화면 (Flask).

대본 확인 -> 사진 순서 확인/재배열 -> 개인정보 마스킹 체크 -> 최종 승인까지
사람이 웹 화면에서 직접 처리합니다. 승인 버튼을 누르기 전에는 렌더링이
진행되지 않습니다 (approval.py 의 게이트가 강제합니다). 이 화면에는
"게시" 버튼이 없습니다 — 완전 무인 발행 기능은 만들지 않습니다.

실행: python review_server.py
접속: http://127.0.0.1:5000
"""
from __future__ import annotations

import os

from flask import Flask, redirect, render_template_string, request, send_from_directory, url_for

import approval
import masking_check
import onsite_project

app = Flask(__name__)

INDEX_TEMPLATE = """
<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><title>기프트클린 검수 화면</title>
<style>
body{font-family:-apple-system,sans-serif;max-width:720px;margin:40px auto;padding:0 16px;color:#222}
a{color:#0b5fff;text-decoration:none} a:hover{text-decoration:underline}
.card{border:1px solid #ddd;border-radius:8px;padding:16px;margin-bottom:12px}
.badge{display:inline-block;padding:2px 8px;border-radius:12px;font-size:12px;margin-left:8px}
.ok{background:#e6f4ea;color:#137333} .no{background:#fce8e6;color:#c5221f}
</style></head><body>
<h1>기프트클린 현장형 숏폼 검수</h1>
<p>projects/ 아래의 프로젝트 목록입니다. 클릭해서 대본·사진순서·개인정보를 확인한 뒤 승인하세요.</p>
{% if not projects %}<p>등록된 프로젝트가 없습니다. 먼저 <code>python onsite_main.py init</code>으로 프로젝트를 만드세요.</p>{% endif %}
{% for p in projects %}
<div class="card">
  <a href="{{ url_for('project_detail', project_id=p.id) }}"><strong>{{ p.id }}</strong></a>
  <span class="badge {{ 'ok' if p.approved else 'no' }}">{{ '승인됨' if p.approved else '미승인' }}</span>
  <div>사진 {{ p.photo_count }}장</div>
</div>
{% endfor %}
</body></html>
"""

DETAIL_TEMPLATE = """
<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><title>{{ project_id }} 검수</title>
<style>
body{font-family:-apple-system,sans-serif;max-width:820px;margin:40px auto;padding:0 16px;color:#222}
a{color:#0b5fff}
.segment{display:flex;gap:16px;border:1px solid #ddd;border-radius:8px;padding:16px;margin-bottom:14px}
.segment img{width:140px;height:249px;object-fit:cover;border-radius:6px;background:#eee}
.phase{font-size:12px;color:#666;text-transform:uppercase}
.script{white-space:pre-wrap;background:#fafafa;border:1px solid #eee;border-radius:6px;padding:10px;margin-top:6px}
.checks label{margin-right:12px;font-size:14px}
.reorder-btn{font-size:12px;padding:2px 8px;margin-right:4px}
.warn{background:#fff4e5;border:1px solid #ffcc80;border-radius:8px;padding:12px;margin-bottom:14px}
.ok-box{background:#e6f4ea;border:1px solid #a8dab5;border-radius:8px;padding:12px;margin-bottom:14px}
button.approve{background:#0b5fff;color:#fff;border:none;padding:10px 18px;border-radius:6px;font-size:15px;cursor:pointer}
button.approve:disabled{background:#aaa;cursor:not-allowed}
</style></head><body>
<p><a href="{{ url_for('index') }}">&larr; 목록으로</a></p>
<h1>{{ project_id }}</h1>

{% if approval_record.approved %}
<div class="ok-box">✅ 승인 완료 — 승인자: {{ approval_record.approved_by }} / {{ approval_record.approved_at }}</div>
{% elif problems %}
<div class="warn"><strong>아직 승인할 수 없습니다:</strong><ul>{% for p in problems %}<li>{{ p }}</li>{% endfor %}</ul></div>
{% endif %}

{% for seg in segments %}
<div class="segment">
  <img src="{{ url_for('photo_file', project_id=project_id, filename=seg.filename) }}">
  <div style="flex:1">
    <div class="phase">[{{ loop.index }}] {{ seg.phase_label }} — {{ seg.filename }}</div>
    <div class="script">{{ seg.text or '(대본 미작성 - script.txt를 채워주세요)' }}</div>

    <form method="post" action="{{ url_for('do_reorder', project_id=project_id) }}" style="margin-top:8px">
      <input type="hidden" name="filename" value="{{ seg.filename }}">
      <button class="reorder-btn" name="direction" value="up" {{ 'disabled' if loop.first else '' }}>위로</button>
      <button class="reorder-btn" name="direction" value="down" {{ 'disabled' if loop.last else '' }}>아래로</button>
    </form>

    <form method="post" action="{{ url_for('do_check', project_id=project_id) }}" class="checks" style="margin-top:8px">
      <input type="hidden" name="filename" value="{{ seg.filename }}">
      {% for field, label in check_fields %}
      <label><input type="checkbox" name="{{ field }}" {{ 'checked' if seg.checklist.get(field) else '' }}> {{ label }} 노출없음</label>
      {% endfor %}
      <button type="submit">체크 저장</button>
    </form>
  </div>
</div>
{% endfor %}

<hr>
<h2>최종 승인</h2>
<form method="post" action="{{ url_for('do_approve', project_id=project_id) }}">
  <label>승인자 이름: <input type="text" name="by" required></label><br><br>
  <label>메모: <input type="text" name="notes" style="width:300px"></label><br><br>
  <button class="approve" type="submit" {{ 'disabled' if problems and not approval_record.approved else '' }}>승인하고 렌더링 허용</button>
</form>
{% if error %}<p style="color:#c5221f">{{ error }}</p>{% endif %}
</body></html>
"""


def _project_ids():
    root = onsite_project.PROJECTS_ROOT
    if not os.path.exists(root):
        return []
    return sorted(
        name for name in os.listdir(root)
        if os.path.isdir(os.path.join(root, name))
    )


@app.route("/")
def index():
    projects = []
    for pid in _project_ids():
        manifest = onsite_project.load_manifest(pid)
        record = approval.load_approval(pid)
        projects.append({"id": pid, "photo_count": len(manifest), "approved": record.get("approved", False)})
    return render_template_string(INDEX_TEMPLATE, projects=projects)


@app.route("/project/<project_id>")
def project_detail(project_id):
    return _render_detail(project_id)


def _render_detail(project_id, error=None):
    masking_check.sync_with_manifest(project_id)
    checklist = masking_check.load_checklist(project_id)
    manifest = onsite_project.sorted_manifest(project_id)
    script_texts = onsite_project.parse_script(project_id, strict=False)

    segments = []
    for item in manifest:
        segments.append({
            "filename": item["filename"],
            "phase": item["phase"],
            "phase_label": onsite_project.PHASE_LABELS[item["phase"]],
            "text": script_texts.get(item["filename"], ""),
            "checklist": checklist.get(item["filename"], {}),
        })

    problems = approval.check_ready(project_id)
    approval_record = approval.load_approval(project_id)

    return render_template_string(
        DETAIL_TEMPLATE,
        project_id=project_id,
        segments=segments,
        problems=problems,
        approval_record=approval_record,
        check_fields=[(f, masking_check.FIELD_LABELS[f]) for f in masking_check.CHECK_FIELDS],
        error=error,
    )


@app.route("/project/<project_id>/photo/<path:filename>")
def photo_file(project_id, filename):
    photos_dir = os.path.join(onsite_project.project_dir(project_id), "photos")
    return send_from_directory(photos_dir, filename)


@app.route("/project/<project_id>/check", methods=["POST"])
def do_check(project_id):
    filename = request.form["filename"]
    flags = {field: (field in request.form) for field in masking_check.CHECK_FIELDS}
    masking_check.update_check(project_id, filename, **flags)
    return redirect(url_for("project_detail", project_id=project_id))


@app.route("/project/<project_id>/reorder", methods=["POST"])
def do_reorder(project_id):
    filename = request.form["filename"]
    direction = request.form["direction"]
    manifest = onsite_project.sorted_manifest(project_id)
    names = [item["filename"] for item in manifest]
    idx = names.index(filename)
    swap_idx = idx - 1 if direction == "up" else idx + 1
    if 0 <= swap_idx < len(names):
        names[idx], names[swap_idx] = names[swap_idx], names[idx]
        onsite_project.reorder_photos(project_id, names)
    return redirect(url_for("project_detail", project_id=project_id))


@app.route("/project/<project_id>/approve", methods=["POST"])
def do_approve(project_id):
    by = request.form.get("by", "")
    notes = request.form.get("notes", "")
    try:
        approval.approve(project_id, by, notes)
    except Exception as e:
        return _render_detail(project_id, error=str(e))
    return redirect(url_for("project_detail", project_id=project_id))


if __name__ == "__main__":
    print("🖥️  검수 화면 실행 중... http://127.0.0.1:5000 접속하세요.")
    app.run(host="127.0.0.1", port=5000, debug=False)
