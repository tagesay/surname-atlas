# -*- coding: utf-8 -*-
"""把《Victory》合成为成片音轨。

用法
----
1. 把音频文件放到 bgm/ 下，命名为 Victory.mp3（也支持 .wav/.m4a/.flac/.ogg/.aac）
2. python add_bgm.py

说明
----
· 绝不用「合成一段听起来像史诗的音乐」来冒充《Victory》——那是欺骗，且
  Two Steps From Hell 的《Victory》是商业版权曲目，本项目不提供下载。
  没有音频文件时脚本会明确报错退出，不生成带假音轨的成片。
· 《Victory》本身的编排就是由平缓铺陈推进到高潮，正好对应最初要求的
  「前期平缓，到现代激昂」；这里只做整体音量、2.5 秒淡入、3 秒淡出，
  不改动曲子的动态。
· 视频流用 -c:v copy 直接复制，不重编码、不重渲染，合成只需几秒。
· 视频因「事件阅读停留帧」降速后（414.7 秒）远长于《Victory》（253.0 秒）。
  若直接循环，第二遍会重新回到平缓前奏，把「前期平缓→现代激昂」的情绪曲线
  打断一次。默认改用 stretch：整曲用 atempo 匀速拉伸到全片长度，一次播完，
  无循环接缝、无第二次前奏，曲目内容与编排完全不变，只是播放速度变慢。
  --mode loop 可切回旧的循环行为做对照。
"""
import argparse
import math
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BGM_DIR = ROOT / "bgm"
VIDEO = ROOT / "video_out" / "surname_century.mp4"
OUT = ROOT / "video_out" / "surname_century_bgm.mp4"
EXTS = (".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac", ".wma", ".opus")

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def probe(path, stream):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", stream,
         "-show_entries", "format=duration" if stream == "a:0" else "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True)
    try:
        return float(r.stdout.strip().splitlines()[0])
    except Exception:
        return None


def find_bgm():
    if not BGM_DIR.exists():
        return None
    hits = [f for f in BGM_DIR.iterdir()
            if f.is_file() and f.stem.lower() == "victory" and f.suffix.lower() in EXTS]
    if not hits:
        # 名字带 Victory 即可，兼容「Victory (Two Steps From Hell).mp3」这类命名
        hits = [f for f in BGM_DIR.iterdir()
                if f.is_file() and "victory" in f.stem.lower() and f.suffix.lower() in EXTS]
    return sorted(hits, key=lambda f: len(f.name))[0] if hits else None


def main():
    ap = argparse.ArgumentParser(description="给姓氏繁衍成片合流《Victory》音轨")
    ap.add_argument("--mode", choices=("stretch", "loop"), default="stretch",
                    help="stretch=整曲拉伸到全片长度（默认，情绪单向推进）；loop=循环补足")
    ap.add_argument("--volume", type=float, default=0.30, help="整体音量，默认 0.30")
    args = ap.parse_args()

    if not VIDEO.exists():
        raise SystemExit("✗ 找不到无声成片 %s" % VIDEO)
    bgm = find_bgm()
    if not bgm:
        BGM_DIR.mkdir(exist_ok=True)
        print("✗ 未找到《Victory》音频文件。")
        print("  请把文件放到：%s" % BGM_DIR)
        print("  命名 Victory.mp3（或 Victory.wav / .m4a / .flac / .ogg / .aac 均可）")
        print("  放好后重跑：python add_bgm.py")
        print("  当前交付的 %s 保持无声，不会混入任何替代音轨。" % VIDEO.name)
        return 1

    vdur = probe(VIDEO, "v:0") or 120.2
    adur = probe(bgm, "a:0")
    print("视频 %.1f 秒 / 音频《%s》%s" %
          (vdur, bgm.name, ("%.1f 秒" % adur) if adur else "时长未知"))
    print("合流模式：%s / 音量 %.2f" % (args.mode, args.volume))

    fade_out_at = max(0.5, vdur - 3.0)
    tail = ("volume=%.2f,afade=t=in:st=0:d=2.5,"
            "afade=t=out:st=%.2f:d=3" % (args.volume, fade_out_at))

    if args.mode == "stretch" and adur and vdur > adur:
        tempo = adur / vdur
        if tempo < 0.5:
            print("！需要的 atempo %.3f 超出 ffmpeg 单次下限 0.5，自动改用 loop 模式。" % tempo)
            args.mode = "loop"
        else:
            print("  整曲 atempo=%.4f 匀速拉伸到 %.1f 秒：一次播完，无循环接缝，"
                  "不会出现第二遍平缓前奏。" % (tempo, vdur))
            filt = ("[1:a]atempo=%.4f,apad,atrim=duration=%.3f,%s[a]"
                    % (tempo, vdur, tail))
            cmd = [
                "ffmpeg", "-y",
                "-i", str(VIDEO),
                "-i", str(bgm),
                "-filter_complex", filt,
                "-map", "0:v:0", "-map", "[a]",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                "-shortest", "-movflags", "+faststart", str(OUT),
            ]
            return run(cmd)

    if adur and vdur > adur:
        print("  视频长于音频，音频将循环 %d 遍覆盖全片（尾部另有 3 秒整体淡出）。"
              % math.ceil(vdur / adur))
    filt = "[1:a]%s[a]" % tail
    cmd = [
        "ffmpeg", "-y",
        "-i", str(VIDEO),
        "-stream_loop", "-1", "-i", str(bgm),
        "-filter_complex", filt,
        "-map", "0:v:0", "-map", "[a]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-shortest", "-movflags", "+faststart", str(OUT),
    ]
    return run(cmd)


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("✗ ffmpeg 合流失败：\n" + (r.stderr or "")[-1600:])
        return 2
    print("✓ 已生成带《Victory》音轨的成片：%s（%.1f MB）" %
          (OUT, OUT.stat().st_size / 1048576))
    print("  原无声版 %s 保留未动。" % VIDEO.name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
