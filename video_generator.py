"""
ffmpeg를 사용하여 슬라이드 이미지를 영상으로 합성합니다.
TTS 오디오가 제공되면 나레이션이 포함된 영상을 생성합니다.
"""

import os
import glob
import subprocess
import shutil


def _check_ffmpeg() -> bool:
    """ffmpeg가 설치되어 있는지 확인합니다."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"], 
            capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _find_bgm(bgm_dir: str = "assets/bgm") -> str | None:
    """BGM 디렉토리에서 음악 파일을 찾습니다."""
    if not os.path.exists(bgm_dir):
        return None
    
    audio_exts = ["*.mp3", "*.wav", "*.m4a", "*.ogg"]
    for ext in audio_exts:
        files = glob.glob(os.path.join(bgm_dir, ext))
        if files:
            return files[0]
    
    return None


def _escape_path_for_filter(path: str) -> str:
    """ffmpeg 필터 옵션(subtitles= 등) 안에 경로를 넣을 때 콜론을 이스케이프합니다."""
    return os.path.abspath(path).replace("\\", "/").replace(":", "\\:")


def _build_subtitle_filter(srt_path: str, margin_v: int = 35) -> str:
    """SRT 자막을 화면 하단 안전영역에 번인하는 subtitles 필터 문자열을 만듭니다.

    margin_v=35는 1080x1920 기준 화면 하단에서 약 200px 위 지점으로,
    쇼츠/릴스 플랫폼 UI(좋아요·공유 버튼 등)와 겹치지 않는 안전영역입니다.
    (참고: 이 값은 libass의 기본 스크립트 해상도 기준 단위이며 실제 픽셀이 아닙니다 —
    임의로 원본 해상도 리터럴 픽셀로 바꾸면 폰트 크기가 예기치 않게 커지므로
    이 기존 스케일을 그대로 사용해 튜닝했습니다.)
    """
    escaped = _escape_path_for_filter(srt_path)
    force_style = (
        "FontName=NanumGothic,FontSize=13,PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H00000000,BorderStyle=3,Outline=1,Shadow=0,"
        f"Alignment=2,MarginV={margin_v}"
    )
    return f"subtitles='{escaped}':force_style='{force_style}'"


def _build_normalize_filter(width: int, height: int, factor: int = 2) -> str:
    """임의 비율의 원본 사진을 목표 해상도의 factor배 크기로 스케일+크롭합니다.
    zoompan 이전에 적용하면 원본 사진의 가로세로 비율과 무관하게
    왜곡 없이 9:16 프레임을 채울 수 있습니다.
    (사전 렌더링된 1080x1920 슬라이드에 적용해도 사실상 변화가 없어 안전합니다.)
    """
    return (
        f"scale=-2:{height * factor}:force_original_aspect_ratio=increase,"
        f"crop={width * factor}:{height * factor}"
    )


def _build_zoom_filter(
    width: int, height: int, fps: int, duration: float,
    transition_duration: float, slide_index: int,
) -> str:
    """
    Ken Burns 효과 (줌인/줌아웃) + 페이드 필터를 생성합니다.
    슬라이드마다 줌 방향이 번갈아가며 바뀝니다.
    """
    total_frames = int(fps * duration)
    fade_frames = int(fps * transition_duration)
    fade_out_start = int(fps * (duration - transition_duration))

    # 이미지를 약간 크게 확대해서 줌 여유 공간 확보
    # 줌인: 1.0 → 1.15 / 줌아웃: 1.15 → 1.0
    if slide_index % 2 == 0:
        # 줌인 (천천히 확대)
        zoom_expr = f"min(1+0.15*on/{total_frames},1.15)"
    else:
        # 줌아웃 (천천히 축소)
        zoom_expr = f"max(1.15-0.15*on/{total_frames},1.0)"

    # zoompan: 원본 이미지를 줌하면서 가운데 유지
    zoompan = (
        f"zoompan=z='{zoom_expr}'"
        f":x='iw/2-(iw/zoom/2)'"
        f":y='ih/2-(ih/zoom/2)'"
        f":d={total_frames}"
        f":s={width}x{height}"
        f":fps={fps}"
    )

    fade_in = f"fade=in:0:{fade_frames}"
    fade_out = f"fade=out:{fade_out_start}:{fade_frames}"

    return f"{zoompan},{fade_in},{fade_out}"


def _create_slide_clip(
    slide_path: str,
    output_path: str,
    duration: float,
    fps: int,
    transition_duration: float,
    tts_path: str | None = None,
    slide_index: int = 0,
    subtitle_path: str | None = None,
    normalize_source: bool = False,
) -> bool:
    """단일 슬라이드/사진을 비디오 클립으로 변환합니다 (Ken Burns 효과 포함).

    normalize_source=True면 원본 사진의 비율이 9:16이 아니어도 스케일+크롭으로
    왜곡 없이 프레임을 채웁니다 (현장형 모드의 실제 사진용).
    subtitle_path가 주어지면 해당 클립 구간에 자막을 번인합니다.
    """
    zoom_vf = _build_zoom_filter(1080, 1920, fps, duration, transition_duration, slide_index)
    vf_parts = []
    if normalize_source:
        vf_parts.append(_build_normalize_filter(1080, 1920, factor=2))
    vf_parts.append(zoom_vf)
    if subtitle_path:
        vf_parts.append(_build_subtitle_filter(subtitle_path))
    vf = ",".join(vf_parts)

    if tts_path:
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", slide_path,
            "-i", tts_path,
            "-c:v", "libx264",
            "-c:a", "aac",
            "-b:a", "192k",
            "-t", str(duration),
            "-pix_fmt", "yuv420p",
            "-r", str(fps),
            "-vf", vf,
            output_path,
        ]
    else:
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", slide_path,
            "-c:v", "libx264",
            "-t", str(duration),
            "-pix_fmt", "yuv420p",
            "-r", str(fps),
            "-vf", vf,
            output_path,
        ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        # fallback: zoompan 없이 기본 fade만 적용
        fade_frames = int(fps * transition_duration)
        fade_out_start = int(fps * (duration - transition_duration))
        simple_parts = [_build_normalize_filter(1080, 1920, factor=1)] if normalize_source else ["scale=1080:1920"]
        simple_parts.append(f"fade=in:0:{fade_frames}")
        simple_parts.append(f"fade=out:{fade_out_start}:{fade_frames}")
        if subtitle_path:
            simple_parts.append(_build_subtitle_filter(subtitle_path))
        simple_vf = ",".join(simple_parts)

        if tts_path:
            cmd_simple = [
                "ffmpeg", "-y",
                "-loop", "1",
                "-i", slide_path,
                "-i", tts_path,
                "-c:v", "libx264",
                "-c:a", "aac",
                "-b:a", "192k",
                "-t", str(duration),
                "-pix_fmt", "yuv420p",
                "-r", str(fps),
                "-vf", simple_vf,
                output_path,
            ]
        else:
            cmd_simple = [
                "ffmpeg", "-y",
                "-loop", "1",
                "-i", slide_path,
                "-c:v", "libx264",
                "-t", str(duration),
                "-pix_fmt", "yuv420p",
                "-r", str(fps),
                "-vf", simple_vf,
                output_path,
            ]
        result = subprocess.run(cmd_simple, capture_output=True, text=True)
        return result.returncode == 0

    return True


def create_video(
    slide_paths: list,
    output_path: str,
    fps: int = 30,
    slide_duration: float = 5.0,
    transition_duration: float = 0.5,
    bgm_enabled: bool = False,
    bgm_volume: float = 0.15,
    tts_data: list | None = None,
) -> str:
    """
    슬라이드 이미지들을 영상으로 합성합니다.
    
    Args:
        slide_paths: 슬라이드 이미지 파일 경로 리스트
        output_path: 출력 영상 파일 경로
        fps: 프레임 레이트
        slide_duration: 각 슬라이드 기본 표시 시간 (초, TTS 없을 때 사용)
        transition_duration: 전환 효과 시간 (초)
        bgm_enabled: 배경음악 사용 여부
        bgm_volume: 배경음악 볼륨
        tts_data: TTS 데이터 리스트 [{"path": str, "duration": float}, ...]
                  None이면 TTS 없이 기존 방식으로 생성
    
    Returns:
        생성된 영상 파일 경로
    """
    if not _check_ffmpeg():
        print("❌ ffmpeg가 설치되어 있지 않습니다!")
        print("   설치 방법:")
        print("   - Windows: https://www.gyan.dev/ffmpeg/builds/")
        print("   - Mac: brew install ffmpeg")
        print("   - Linux: sudo apt install ffmpeg")
        raise RuntimeError("ffmpeg not found")
    
    if not slide_paths:
        raise ValueError("슬라이드가 없습니다!")
    
    has_tts = tts_data is not None and len(tts_data) == len(slide_paths)
    
    if has_tts:
        print("🎬 영상 생성 중... (TTS 나레이션 포함)")
    else:
        print("🎬 영상 생성 중...")
    
    temp_dir = os.path.dirname(slide_paths[0])
    temp_videos = []
    
    # 1단계: 각 슬라이드를 개별 비디오 클립으로 변환
    for i, slide_path in enumerate(slide_paths):
        temp_video = os.path.join(temp_dir, f"clip_{i:03d}.mp4")

        # TTS가 있으면 오디오 길이 기반으로 슬라이드 시간 결정
        if has_tts:
            tts_info = tts_data[i]
            tts_path = tts_info["path"]
            # TTS 길이 + 여유 시간 (최소 slide_duration)
            clip_duration = max(tts_info["duration"] + 0.5, slide_duration)
        else:
            tts_path = None
            clip_duration = slide_duration

        success = _create_slide_clip(
            slide_path=slide_path,
            output_path=temp_video,
            duration=clip_duration,
            fps=fps,
            transition_duration=transition_duration,
            tts_path=tts_path,
            slide_index=i,
        )
        
        if not success:
            print(f"  ⚠️  슬라이드 {i+1} 변환 중 오류 발생")
        
        temp_videos.append(temp_video)
        duration_str = f" ({clip_duration:.1f}초)" if has_tts else ""
        print(f"  📹 슬라이드 {i+1}/{len(slide_paths)} 변환 완료{duration_str}")
    
    # 2단계: concat 파일 생성
    concat_file = os.path.join(temp_dir, "concat_list.txt")
    with open(concat_file, "w") as f:
        for video in temp_videos:
            f.write(f"file '{os.path.abspath(video)}'\n")
    
    # 3단계: 영상 합치기
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    
    # TTS가 있는 경우 concat 방식이 다름 (오디오 포함)
    if has_tts:
        # TTS 오디오가 포함된 클립들을 합치기
        concat_cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", concat_file,
            "-c:v", "libx264",
            "-c:a", "aac",
            "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
        ]
        
        if bgm_enabled:
            bgm_path = _find_bgm()
            if bgm_path:
                print(f"  🎵 배경음악 적용: {os.path.basename(bgm_path)}")
                # TTS + BGM 믹싱: TTS 볼륨 유지, BGM 볼륨 낮춤
                temp_no_bgm = os.path.join(temp_dir, "temp_no_bgm.mp4")
                concat_cmd.append(temp_no_bgm)
                
                print("  🔧 TTS 영상 렌더링 중...")
                result = subprocess.run(concat_cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    raise RuntimeError(f"concat failed: {result.stderr[:200]}")
                
                # BGM 믹싱
                print("  🎵 TTS + BGM 믹싱 중...")
                mix_cmd = [
                    "ffmpeg", "-y",
                    "-i", temp_no_bgm,
                    "-i", bgm_path,
                    "-filter_complex",
                    f"[0:a]volume=1.0[tts];[1:a]volume={bgm_volume}[bgm];"
                    f"[tts][bgm]amix=inputs=2:duration=first[a]",
                    "-map", "0:v",
                    "-map", "[a]",
                    "-c:v", "copy",
                    "-c:a", "aac",
                    "-b:a", "192k",
                    "-movflags", "+faststart",
                    output_path,
                ]
                print("  🔧 최종 영상 렌더링 중...")
                result = subprocess.run(mix_cmd, capture_output=True, text=True)
            else:
                print("  ⚠️  BGM 파일을 찾을 수 없어 TTS만 사용합니다.")
                concat_cmd.append(output_path)
                print("  🔧 최종 영상 렌더링 중...")
                result = subprocess.run(concat_cmd, capture_output=True, text=True)
        else:
            concat_cmd.append(output_path)
            print("  🔧 최종 영상 렌더링 중...")
            result = subprocess.run(concat_cmd, capture_output=True, text=True)
    else:
        # TTS 없는 기존 방식
        if bgm_enabled:
            bgm_path = _find_bgm()
            if bgm_path:
                print(f"  🎵 배경음악 적용: {os.path.basename(bgm_path)}")
                cmd = [
                    "ffmpeg", "-y",
                    "-f", "concat", "-safe", "0", "-i", concat_file,
                    "-i", bgm_path,
                    "-c:v", "libx264",
                    "-c:a", "aac",
                    "-b:a", "128k",
                    "-filter_complex", f"[1:a]volume={bgm_volume}[bgm];[bgm]apad[a]",
                    "-map", "0:v",
                    "-map", "[a]",
                    "-shortest",
                    "-pix_fmt", "yuv420p",
                    output_path,
                ]
            else:
                print("  ⚠️  BGM 파일을 찾을 수 없어 음악 없이 생성합니다.")
                bgm_enabled = False
        
        if not bgm_enabled:
            cmd = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0", "-i", concat_file,
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                output_path,
            ]
        
        print("  🔧 최종 영상 렌더링 중...")
        result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"❌ 영상 생성 실패: {result.stderr[:500]}")
        raise RuntimeError(f"ffmpeg failed: {result.stderr[:200]}")
    
    # 4단계: 임시 파일 정리
    print("  🧹 임시 파일 정리 중...")
    try:
        # 슬라이드 임시 디렉토리
        shutil.rmtree(temp_dir)
    except Exception:
        pass
    
    # TTS 임시 디렉토리도 정리
    tts_temp_dir = os.path.join(os.path.dirname(output_path), "_temp_tts")
    if os.path.exists(tts_temp_dir):
        try:
            shutil.rmtree(tts_temp_dir)
        except Exception:
            pass
    
    # 결과 확인
    if os.path.exists(output_path):
        file_size = os.path.getsize(output_path) / (1024 * 1024)  # MB
        print(f"✅ 영상 생성 완료!")
        print(f"   📁 파일: {output_path}")
        print(f"   📊 크기: {file_size:.1f} MB")
        return output_path
    else:
        raise RuntimeError("영상 파일이 생성되지 않았습니다.")


def _create_static_clip_with_silence(image_path: str, duration: float, output_path: str,
                                      fps: int = 30, width: int = 1080, height: int = 1920) -> str:
    """이미지 한 장 + 무음 오디오 트랙으로 정적 클립을 만듭니다 (CTA 엔딩 등).
    다른 클립들과 동일한 코덱/스트림 구성이라 concat 이어붙이기가 안전합니다.
    """
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", image_path,
        "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
        "-t", f"{duration:.3f}",
        "-vf", f"scale={width}:{height}",
        "-c:v", "libx264", "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p", "-r", str(fps),
        "-shortest",
        output_path,
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path


def _overlay_logo(video_path: str, logo_path: str, output_path: str,
                   margin: int = 30, logo_width: int = 160) -> str:
    """영상 우상단에 로고를 작게 오버레이합니다."""
    filter_complex = (
        f"[1:v]scale={logo_width}:-1[logo];"
        f"[0:v][logo]overlay=W-w-{margin}:{margin}"
    )
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", logo_path,
        "-filter_complex", filter_complex,
        "-map", "0:a?",
        "-c:v", "libx264", "-c:a", "copy",
        "-pix_fmt", "yuv420p",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"로고 오버레이 실패: {result.stderr[:300]}")
    return output_path


def _mix_bgm(video_path: str, bgm_path: str, bgm_volume: float, output_path: str) -> str:
    """나레이션 오디오에 배경음악을 낮은 볼륨으로 믹싱합니다."""
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-stream_loop", "-1", "-i", bgm_path,
        "-filter_complex",
        f"[0:a]volume=1.0[narration];[1:a]volume={bgm_volume}[bgm];"
        f"[narration][bgm]amix=inputs=2:duration=first:dropout_transition=0[a]",
        "-map", "0:v",
        "-map", "[a]",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"배경음악 믹싱 실패: {result.stderr[:300]}")
    return output_path


def create_onsite_video(
    photo_paths: list,
    output_path: str,
    tts_data: list,
    subtitle_paths: list | None = None,
    fps: int = 30,
    transition_duration: float = 0.5,
    min_duration: float = 2.5,
    duration_overrides: list | None = None,
    cta_image_path: str | None = None,
    cta_duration: float = 3.0,
    logo_path: str | None = None,
    bgm_path: str | None = None,
    bgm_volume: float = 0.12,
) -> str:
    """현장형(Before/작업중/After 사진) 숏폼 영상을 합성합니다.

    photo_paths, tts_data, subtitle_paths는 반드시 같은 순서로 1:1 대응해야
    합니다 (사진 순서 = 대본 문단 순서 = 나레이션/자막 순서). 사진은 원본
    비율과 무관하게 스케일+크롭으로 9:16 프레임에 왜곡 없이 채워집니다.

    duration_overrides: 사진별 최소 노출시간(초) 리스트. 값이 None인 항목은
        min_duration을 사용합니다 (나레이션이 더 길면 나레이션 길이가 우선).
    cta_image_path: 마지막에 붙일 CTA(브랜드 각인) 슬라이드 이미지. 무음 처리됩니다.
    logo_path: 영상 전체에 우상단으로 작게 오버레이할 로고 PNG (투명배경 권장).
    bgm_path: 배경음악 파일. 지정하면 나레이션과 낮은 볼륨으로 믹싱합니다.
    """
    if not _check_ffmpeg():
        print("❌ ffmpeg가 설치되어 있지 않습니다!")
        raise RuntimeError("ffmpeg not found")

    if not photo_paths:
        raise ValueError("사진이 없습니다!")

    if len(tts_data) != len(photo_paths):
        raise ValueError(
            f"사진 수({len(photo_paths)})와 나레이션 수({len(tts_data)})가 일치하지 않습니다. "
            "사진 순서와 대본 문단 수를 맞춰주세요."
        )

    if subtitle_paths is not None and len(subtitle_paths) != len(photo_paths):
        raise ValueError("자막 파일 수가 사진 수와 일치하지 않습니다.")

    if duration_overrides is not None and len(duration_overrides) != len(photo_paths):
        raise ValueError("사진별 노출시간 목록 수가 사진 수와 일치하지 않습니다.")

    print("🎬 현장형 영상 생성 중... (사진 + TTS 나레이션 + 자막)")

    out_dir = os.path.dirname(output_path) or "."
    os.makedirs(out_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(output_path))[0]
    temp_dir = os.path.join(out_dir, f"_temp_onsite_{base_name}")
    os.makedirs(temp_dir, exist_ok=True)

    temp_videos = []
    for i, photo_path in enumerate(photo_paths):
        tts_info = tts_data[i]
        floor_duration = min_duration
        if duration_overrides is not None and duration_overrides[i]:
            floor_duration = duration_overrides[i]
        clip_duration = max(tts_info["duration"] + 0.5, floor_duration)
        subtitle_path = subtitle_paths[i] if subtitle_paths else None

        temp_video = os.path.join(temp_dir, f"clip_{i:03d}.mp4")
        success = _create_slide_clip(
            slide_path=photo_path,
            output_path=temp_video,
            duration=clip_duration,
            fps=fps,
            transition_duration=transition_duration,
            tts_path=tts_info["path"],
            slide_index=i,
            subtitle_path=subtitle_path,
            normalize_source=True,
        )
        if not success:
            print(f"  ⚠️  사진 {i + 1} 변환 중 오류 발생")
        temp_videos.append(temp_video)
        print(f"  📹 사진 {i + 1}/{len(photo_paths)} 변환 완료 ({clip_duration:.1f}초)")

    if cta_image_path:
        cta_clip = os.path.join(temp_dir, "clip_cta.mp4")
        _create_static_clip_with_silence(cta_image_path, cta_duration, cta_clip, fps)
        temp_videos.append(cta_clip)
        print(f"  📹 CTA 엔딩 슬라이드 추가 ({cta_duration:.1f}초)")

    concat_file = os.path.join(temp_dir, "concat_list.txt")
    with open(concat_file, "w") as f:
        for video in temp_videos:
            f.write(f"file '{os.path.abspath(video)}'\n")

    needs_postprocess = bool(logo_path or bgm_path)
    concat_output = os.path.join(temp_dir, "concat_raw.mp4") if needs_postprocess else output_path

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", concat_file,
        "-c:v", "libx264",
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        concat_output,
    ]
    print("  🔧 클립 합치는 중...")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"❌ 영상 생성 실패: {result.stderr[:500]}")
        raise RuntimeError(f"ffmpeg failed: {result.stderr[:200]}")

    current = concat_output

    if logo_path:
        print("  🏷️  로고 오버레이 적용 중...")
        logo_output = os.path.join(temp_dir, "with_logo.mp4") if bgm_path else output_path
        _overlay_logo(current, logo_path, logo_output)
        current = logo_output

    if bgm_path:
        print(f"  🎵 배경음악 믹싱 중... ({os.path.basename(bgm_path)})")
        _mix_bgm(current, bgm_path, bgm_volume, output_path)
        current = output_path

    if current != output_path:
        shutil.move(current, output_path)

    print("  🧹 임시 파일 정리 중...")
    try:
        shutil.rmtree(temp_dir)
    except Exception:
        pass

    if os.path.exists(output_path):
        file_size = os.path.getsize(output_path) / (1024 * 1024)
        print("✅ 현장형 영상 생성 완료!")
        print(f"   📁 파일: {output_path}")
        print(f"   📊 크기: {file_size:.1f} MB")
        return output_path
    else:
        raise RuntimeError("영상 파일이 생성되지 않았습니다.")
