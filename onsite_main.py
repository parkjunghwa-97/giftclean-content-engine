"""
🎬 기프트클린 현장형 숏폼 생성기 (1차 MVP)

Before / 작업 중 / After 사진을 순서대로 등록하고, 사용자가 직접 작성한
대본으로 TTS 나레이션 + SRT 자막을 만든 뒤, 사람이 검수/승인해야만
9:16 최종 영상을 렌더링합니다. 완전 무인 게시 기능은 없습니다.

사용법 요약:
    python onsite_main.py init --project my-site-001 \\
        --photo before.jpg:before --photo work.jpg:during --photo after.jpg:after

    # projects/my-site-001/script.txt 를 열어 대본을 작성한 뒤:
    python onsite_main.py audio --project my-site-001
    python onsite_main.py check --project my-site-001 --photo 00_before.jpg \\
        --face yes --address yes --nameplate yes --mail yes
    python onsite_main.py review --project my-site-001
    python onsite_main.py approve --project my-site-001 --by "홍길동"
    python onsite_main.py render --project my-site-001
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime

import approval
import masking_check
import onsite_branding
import onsite_project
import subtitle_generator
from tts_generator import VOICES, _get_audio_duration, generate_tts, resolve_voice
from video_generator import create_onsite_video

DEFAULT_VOICE = "ko-female"
DEFAULT_RATE = "+0%"
OUTPUT_DIR = "output"


def _tts_manifest_path(project_id: str) -> str:
    return os.path.join(onsite_project.project_dir(project_id), "tts_manifest.json")


def _parse_photo_arg(value: str):
    if ":" not in value:
        raise argparse.ArgumentTypeError(
            f"--photo 값은 '경로:phase' 형식이어야 합니다 (예: before.jpg:before): {value}"
        )
    path, phase = value.rsplit(":", 1)
    return path, phase


def cmd_init(args):
    photos = [_parse_photo_arg(p) for p in args.photo]
    items = onsite_project.import_photos(args.project, photos)

    print(f"✅ 프로젝트 '{args.project}' 생성 완료 — 사진 {len(items)}장 등록됨")
    for item in items:
        print(f"   [{item['order'] + 1}] {onsite_project.PHASE_LABELS[item['phase']]:12s} "
              f"{item['filename']}  (원본: {item['original_name']})")
    script_path = onsite_project.script_path(args.project)
    print()
    print(f"📝 다음 단계: {script_path} 파일을 열어 각 사진에 대한 실제 현장 대본을 작성하세요.")


def cmd_list(args):
    items = onsite_project.sorted_manifest(args.project)
    if not items:
        print("등록된 사진이 없습니다. init 명령으로 먼저 등록하세요.")
        return
    print(f"프로젝트 '{args.project}' 사진 순서:")
    for item in items:
        print(f"  [{item['order'] + 1}] {onsite_project.PHASE_LABELS[item['phase']]:12s} {item['filename']}")


def cmd_reorder(args):
    items = onsite_project.reorder_photos(args.project, args.order)
    print("✅ 사진 순서를 변경했습니다:")
    for item in items:
        print(f"  [{item['order'] + 1}] {onsite_project.PHASE_LABELS[item['phase']]:12s} {item['filename']}")
    print("   (script.txt의 문단도 사진에 맞춰 자동으로 재정렬되었습니다)")


def cmd_check(args):
    masking_check.sync_with_manifest(args.project)
    flags = {}
    for field in masking_check.CHECK_FIELDS:
        value = getattr(args, field)
        if value is not None:
            flags[field] = value.lower() in ("yes", "y", "true", "1")
    checklist = masking_check.update_check(args.project, args.photo, **flags)
    entry = checklist[args.photo]
    print(f"'{args.photo}' 개인정보 체크 상태:")
    for field in masking_check.CHECK_FIELDS:
        mark = "✅" if entry.get(field) else "❌"
        print(f"   {mark} {masking_check.FIELD_LABELS[field]} 노출 없음/마스킹 완료")


def cmd_set_duration(args):
    seconds = args.seconds if args.seconds > 0 else None
    onsite_project.set_duration_override(args.project, args.photo, seconds)
    if seconds:
        print(f"✅ '{args.photo}' 최소 노출시간을 {seconds:.1f}초로 지정했습니다. "
              f"(나레이션이 더 길면 나레이션 길이가 우선 적용됩니다)")
    else:
        print(f"✅ '{args.photo}' 노출시간을 기본값으로 되돌렸습니다.")


def cmd_audio(args):
    segments = onsite_project.ordered_script_segments(args.project)
    voice = resolve_voice(args.voice)

    audio_dir = os.path.join(onsite_project.project_dir(args.project), "audio")
    srt_dir = os.path.join(onsite_project.project_dir(args.project), "subtitles")
    os.makedirs(audio_dir, exist_ok=True)
    os.makedirs(srt_dir, exist_ok=True)

    tts_manifest = []
    for i, seg in enumerate(segments):
        audio_path = os.path.join(audio_dir, f"seg_{i:02d}.mp3")
        print(f"🔊 [{i + 1}/{len(segments)}] {seg['filename']} 나레이션 생성 중...")
        _, duration = generate_tts(seg["text"], voice, audio_path, args.rate)

        srt_path = os.path.join(srt_dir, f"seg_{i:02d}.srt")
        subtitle_generator.generate_segment_srt(seg["text"], duration, srt_path)

        tts_manifest.append({
            "filename": seg["filename"],
            "photo_path": seg["path"],
            "audio_path": audio_path,
            "srt_path": srt_path,
            "duration": duration,
        })

    with open(_tts_manifest_path(args.project), "w", encoding="utf-8") as f:
        json.dump(tts_manifest, f, ensure_ascii=False, indent=2)

    print(f"✅ 나레이션 {len(tts_manifest)}개 + 자막 생성 완료")


def cmd_import_audio(args):
    """edge-tts/오프라인 TTS가 모두 안 될 때, 직접 녹음한 오디오 파일을 그 사진 자리에 넣는다."""
    manifest = onsite_project.sorted_manifest(args.project)
    match = next((m for m in manifest if m["filename"] == args.photo), None)
    if not match:
        print(f"❌ 매니페스트에 없는 사진입니다: {args.photo} (list 명령으로 확인)")
        sys.exit(1)
    if not os.path.exists(args.audio):
        print(f"❌ 오디오 파일을 찾을 수 없습니다: {args.audio}")
        sys.exit(1)

    audio_dir = os.path.join(onsite_project.project_dir(args.project), "audio")
    srt_dir = os.path.join(onsite_project.project_dir(args.project), "subtitles")
    os.makedirs(audio_dir, exist_ok=True)
    os.makedirs(srt_dir, exist_ok=True)

    audio_path = os.path.join(audio_dir, f"seg_{match['order']:02d}.mp3")
    result = subprocess.run(
        ["ffmpeg", "-y", "-i", args.audio, audio_path], capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"❌ 오디오 변환 실패: {result.stderr[:300]}")
        sys.exit(1)
    duration = _get_audio_duration(audio_path)

    script_texts = onsite_project.parse_script(args.project, strict=False)
    text = script_texts.get(args.photo, "")
    srt_path = os.path.join(srt_dir, f"seg_{match['order']:02d}.srt")
    subtitle_generator.generate_segment_srt(text, duration, srt_path)

    manifest_path = _tts_manifest_path(args.project)
    tts_manifest = []
    if os.path.exists(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as f:
            tts_manifest = json.load(f)

    tts_manifest = [e for e in tts_manifest if e["filename"] != args.photo]
    tts_manifest.append({
        "filename": match["filename"],
        "photo_path": match["path"],
        "audio_path": audio_path,
        "srt_path": srt_path,
        "duration": duration,
    })
    order_by_filename = {m["filename"]: m["order"] for m in manifest}
    tts_manifest.sort(key=lambda e: order_by_filename.get(e["filename"], 0))

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(tts_manifest, f, ensure_ascii=False, indent=2)

    print(f"✅ '{args.photo}' 오디오를 직접 녹음한 파일로 교체했습니다 (길이 {duration:.1f}초)")
    if len(tts_manifest) < len(manifest):
        missing = [m["filename"] for m in manifest if m["filename"] not in {e['filename'] for e in tts_manifest}]
        print(f"⚠️  아직 나머지 사진의 오디오가 없습니다: {missing} (audio 명령 또는 import-audio로 채우세요)")


def _build_review_packet(project_id: str) -> str:
    lines = [f"# 검수 패킷 — {project_id}", ""]

    lines.append("## 사진 순서 및 대본")
    try:
        segments = onsite_project.ordered_script_segments(project_id)
        for i, seg in enumerate(segments):
            lines.append(f"[{i + 1}] {onsite_project.PHASE_LABELS[seg['phase']]} — {seg['filename']}")
            lines.append(f"    {seg['text']}")
    except Exception as e:
        lines.append(f"(대본 확인 필요: {e})")
    lines.append("")

    lines.append("## 개인정보 마스킹 체크")
    masking_check.sync_with_manifest(project_id)
    checklist = masking_check.load_checklist(project_id)
    for filename, entry in checklist.items():
        status = "통과" if all(entry.get(f, False) for f in masking_check.CHECK_FIELDS) else "미완료"
        lines.append(f"  {filename}: {status}")
    lines.append("")

    lines.append("## 최종 승인")
    rec = approval.load_approval(project_id)
    if rec.get("approved"):
        lines.append(f"  승인됨 — 승인자: {rec['approved_by']} / 일시: {rec['approved_at']}")
    else:
        problems = approval.check_ready(project_id)
        lines.append("  미승인")
        for p in problems:
            lines.append(f"    - {p}")

    packet = "\n".join(lines)
    path = os.path.join(onsite_project.project_dir(project_id), "review_packet.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(packet)
    return path


def cmd_review(args):
    path = _build_review_packet(args.project)
    with open(path, "r", encoding="utf-8") as f:
        print(f.read())
    print()
    print(f"📄 검수 패킷 저장됨: {path}")
    print("💡 사진과 함께 눈으로 확인하려면: python review_server.py 실행 후 브라우저 접속")


def cmd_approve(args):
    record = approval.approve(args.project, args.by, args.notes or "")
    print(f"✅ 승인 완료 — 승인자: {record['approved_by']} / 일시: {record['approved_at']}")


def cmd_render(args):
    approval.enforce_or_raise(args.project)

    manifest_path = _tts_manifest_path(args.project)
    if not os.path.exists(manifest_path):
        print("❌ 나레이션이 아직 생성되지 않았습니다. 먼저 audio 명령을 실행하세요.")
        sys.exit(1)

    with open(manifest_path, "r", encoding="utf-8") as f:
        tts_manifest = json.load(f)

    photo_paths = [item["photo_path"] for item in tts_manifest]
    tts_data = [{"path": item["audio_path"], "duration": item["duration"]} for item in tts_manifest]
    subtitle_paths = [item["srt_path"] for item in tts_manifest]

    manifest_by_filename = {item["filename"]: item for item in onsite_project.load_manifest(args.project)}
    duration_overrides = [
        manifest_by_filename.get(item["filename"], {}).get("duration_override")
        for item in tts_manifest
    ]

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    today = datetime.now().strftime("%Y%m%d")
    output_path = args.output or os.path.join(OUTPUT_DIR, f"onsite_{args.project}_{today}.mp4")

    logo_path = None
    if not args.no_logo:
        logo_path = onsite_branding.resolve_logo_path(args.logo)
        if args.logo and not logo_path:
            print(f"⚠️  지정한 로고 파일을 찾을 수 없어 로고 없이 진행합니다: {args.logo}")

    cta_image_path = None
    if not args.no_cta:
        cta_dir = os.path.join(onsite_project.project_dir(args.project), "branding")
        os.makedirs(cta_dir, exist_ok=True)
        cta_image_path = onsite_branding.create_cta_slide(
            os.path.join(cta_dir, "cta.png"),
            main_text=args.cta_text,
            sub_text=args.cta_subtext,
        )

    bgm_path = None
    if args.bgm and args.bgm.lower() != "off":
        name = None if args.bgm == "auto" else args.bgm
        bgm_path = onsite_branding.find_bgm(name)
        if not bgm_path:
            print(f"⚠️  배경음악 파일을 찾을 수 없어 BGM 없이 진행합니다 (assets/bgm/ 확인).")

    result_path = create_onsite_video(
        photo_paths=photo_paths,
        output_path=output_path,
        tts_data=tts_data,
        subtitle_paths=subtitle_paths,
        fps=args.fps,
        transition_duration=args.transition,
        duration_overrides=duration_overrides,
        cta_image_path=cta_image_path,
        cta_duration=args.cta_duration,
        logo_path=logo_path,
        bgm_path=bgm_path,
        bgm_volume=args.bgm_volume,
    )
    print()
    print("=" * 50)
    print("🎉 현장형 숏폼 영상 생성 완료!")
    print(f"📁 파일 위치: {result_path}")
    print("=" * 50)


def build_parser():
    parser = argparse.ArgumentParser(
        description="🎬 기프트클린 현장형 숏폼 생성기 (1차 MVP)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="프로젝트 생성 + 사진 등록 (순서 = --photo 입력 순서)")
    p_init.add_argument("--project", required=True, help="프로젝트 ID (폴더명으로 사용)")
    p_init.add_argument("--photo", action="append", required=True,
                         help="사진경로:phase (phase는 before|during|after), 여러 번 지정 가능")
    p_init.set_defaults(func=cmd_init)

    p_list = sub.add_parser("list", help="현재 사진 순서 확인")
    p_list.add_argument("--project", required=True)
    p_list.set_defaults(func=cmd_list)

    p_reorder = sub.add_parser("reorder", help="사진 순서 재지정")
    p_reorder.add_argument("--project", required=True)
    p_reorder.add_argument("--order", nargs="+", required=True, help="새 순서대로 나열한 파일명 목록")
    p_reorder.set_defaults(func=cmd_reorder)

    p_check = sub.add_parser("check", help="사진별 개인정보 마스킹 체크")
    p_check.add_argument("--project", required=True)
    p_check.add_argument("--photo", required=True, help="파일명 (list 명령으로 확인)")
    p_check.add_argument("--face", choices=["yes", "no"])
    p_check.add_argument("--address", choices=["yes", "no"])
    p_check.add_argument("--nameplate", choices=["yes", "no"])
    p_check.add_argument("--mail", choices=["yes", "no"])
    p_check.set_defaults(func=cmd_check)

    p_duration = sub.add_parser("set-duration", help="사진별 최소 노출시간(초) 지정")
    p_duration.add_argument("--project", required=True)
    p_duration.add_argument("--photo", required=True, help="파일명 (list 명령으로 확인)")
    p_duration.add_argument("--seconds", type=float, required=True,
                             help="최소 노출시간(초). 0 이하면 기본값으로 되돌림")
    p_duration.set_defaults(func=cmd_set_duration)

    p_audio = sub.add_parser("audio", help="script.txt 기반 TTS 나레이션 + SRT 자막 생성")
    p_audio.add_argument("--project", required=True)
    p_audio.add_argument("--voice", default=DEFAULT_VOICE, choices=list(VOICES.keys()) + list(VOICES.values()))
    p_audio.add_argument("--rate", default=DEFAULT_RATE)
    p_audio.set_defaults(func=cmd_audio)

    p_import_audio = sub.add_parser(
        "import-audio",
        help="edge-tts/오프라인 TTS가 모두 실패할 때 직접 녹음한 오디오 파일로 대체",
    )
    p_import_audio.add_argument("--project", required=True)
    p_import_audio.add_argument("--photo", required=True, help="파일명 (list 명령으로 확인)")
    p_import_audio.add_argument("--audio", required=True, help="직접 녹음한 음성 파일 경로 (mp3/wav/m4a 등)")
    p_import_audio.set_defaults(func=cmd_import_audio)

    p_review = sub.add_parser("review", help="검수 패킷(대본+체크리스트+승인상태) 출력")
    p_review.add_argument("--project", required=True)
    p_review.set_defaults(func=cmd_review)

    p_approve = sub.add_parser("approve", help="최종 승인 (렌더링 허용)")
    p_approve.add_argument("--project", required=True)
    p_approve.add_argument("--by", required=True, help="승인자 이름")
    p_approve.add_argument("--notes", default="")
    p_approve.set_defaults(func=cmd_approve)

    p_render = sub.add_parser("render", help="최종 9:16 MP4 렌더링 (승인 필요)")
    p_render.add_argument("--project", required=True)
    p_render.add_argument("--output", default=None)
    p_render.add_argument("--fps", type=int, default=30)
    p_render.add_argument("--transition", type=float, default=0.5)
    p_render.add_argument("--logo", default=None,
                           help="로고 PNG 경로 (기본: assets/logo.png 있으면 자동 사용)")
    p_render.add_argument("--no-logo", action="store_true", help="로고 오버레이 끄기")
    p_render.add_argument("--cta-text", default=None, help="CTA 슬라이드 메인 문구")
    p_render.add_argument("--cta-subtext", default=None, help="CTA 슬라이드 보조 문구")
    p_render.add_argument("--cta-duration", type=float, default=3.0, help="CTA 슬라이드 노출시간(초)")
    p_render.add_argument("--no-cta", action="store_true", help="CTA 엔딩 슬라이드 끄기")
    p_render.add_argument("--bgm", default="off",
                           help="배경음악: off(기본) | auto(assets/bgm 첫 곡) | 파일명/경로")
    p_render.add_argument("--bgm-volume", type=float, default=0.12, help="배경음악 볼륨(0.0~1.0)")
    p_render.set_defaults(func=cmd_render)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
    except (ValueError, FileNotFoundError, RuntimeError, PermissionError) as e:
        print(f"❌ {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
