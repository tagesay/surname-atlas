# -*- coding: utf-8 -*-
"""
百家姓地理热力 · 构建脚本

数据（surnames.json 示意骨架 + sources.json 可引用来源 + evidence.json 可考记录证据层）
与渲染（index.template.html）分离。
扩展百家姓：只改 surnames.json，重跑本脚本即可。
三类数据物理隔离，避免把「示意」误当成「可引用统计」，
也避免把「当代官方结论」误当成「历史逐期记录」。

用法：
    python build.py                      # 生成全量交互样品 index.html
    python build.py --list               # 列出当前姓氏
    python build.py --surname 李          # 只出「李」姓的单姓页面（参数化出片的数据侧原型）
    python build.py --surname li --out 李姓.html
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_FILE = ROOT / "surnames.json"
SOURCES_FILE = ROOT / "sources.json"
EVIDENCE_FILE = ROOT / "evidence.json"
PLACES_FILE = ROOT / "places.json"
GENEALOGY_FILE = ROOT / "genealogy.json"
TIMELINE_FILE = ROOT / "timeline.json"
CENTURY_FILE = ROOT / "century_atlas.json"
EVENTS_FILE = ROOT / "migration_events.json"
TEMPLATE_FILE = ROOT / "index.template.html"
CINEMA_TEMPLATE_FILE = ROOT / "cinema.template.html"
H5_TEMPLATE_FILE = ROOT / "h5.template.html"
H5_CORE_FILE = ROOT / "h5data" / "core.js"
H5_PLACEHOLDER = "__H5_CORE_JSON__"
PLACEHOLDER = "__ATLAS_DATA__"
SOURCES_PLACEHOLDER = "__ATLAS_SOURCES__"
EVIDENCE_PLACEHOLDER = "__ATLAS_EVIDENCE__"
PLACES_PLACEHOLDER = "__ATLAS_PLACES__"
GENEALOGY_PLACEHOLDER = "__ATLAS_GENEALOGY__"
CINEMA_PLACEHOLDERS = {
    "__ATLAS_TIMELINE__": TIMELINE_FILE,
    "__ATLAS_CENTURY__":  CENTURY_FILE,
    "__ATLAS_EVENTS__":   EVENTS_FILE,
    "__ATLAS_PLACES__":   PLACES_FILE,
}

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def load_data():
    with DATA_FILE.open(encoding="utf-8") as f:
        return json.load(f)


def load_sources():
    """可引用来源清单缺失时降级为空对象，不阻断示意页面生成。"""
    if not SOURCES_FILE.exists():
        return {"meta": {}, "sources": [], "facts": [], "limits": [],
                "provinceTopSurname2019": {"bySurname": {}, "notAnalyzed": []}}
    with SOURCES_FILE.open(encoding="utf-8") as f:
        return json.load(f)


def load_evidence():
    """可考记录证据层：逐姓接入，缺失时降级为空，不阻断示意页面生成。"""
    if not EVIDENCE_FILE.exists():
        return {"meta": {}, "sources": [], "acquisition": [], "surnames": {}}
    with EVIDENCE_FILE.open(encoding="utf-8") as f:
        return json.load(f)


def load_places():
    """基底层：全国行政单元中心点。缺失时降级为空，不阻断页面生成。"""
    if not PLACES_FILE.exists():
        return {}
    with PLACES_FILE.open(encoding="utf-8") as f:
        return json.load(f)


def load_genealogy():
    """史料核实的姓氏聚居时间线。缺失时降级为空，不阻断页面生成。"""
    if not GENEALOGY_FILE.exists():
        return {"meta": {}, "surnames": {}}
    with GENEALOGY_FILE.open(encoding="utf-8") as f:
        return json.load(f)


def inline_json(obj):
    """内嵌 JSON 时转义 </，防止提前闭合 <script>。"""
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def build_cinema():
    """生成 34 格百年时间轴的纯可视化出片页 cinema.html。

    与 index.html（交互核查页）完全分离：
      · index.html   —— 5 期示意骨架 + 权威数据核查面板，供人查证
      · cinema.html  —— 34 格共用时间轴 + 事件驱动点密度，无口播、无字幕，供逐帧出片
    两页共用同一份 places.json / century_atlas.json，不会各说各话。
    """
    if not CINEMA_TEMPLATE_FILE.exists():
        print("  ⚠ 未找到 cinema.template.html，跳过出片页")
        return None
    tpl = CINEMA_TEMPLATE_FILE.read_text(encoding="utf-8")
    missing = [p for p in CINEMA_PLACEHOLDERS if p not in tpl]
    if missing:
        raise SystemExit("出片模板缺少占位符 %s" % "、".join(missing))
    for ph, f in CINEMA_PLACEHOLDERS.items():
        if not f.exists():
            raise SystemExit("出片数据缺失：%s，请先运行 build_timeline.py / build_century_atlas.py" % f.name)
        with f.open(encoding="utf-8") as fh:
            tpl = tpl.replace(ph, inline_json(json.load(fh)))
    out = ROOT / "cinema.html"
    out.write_text(tpl, encoding="utf-8")
    with CENTURY_FILE.open(encoding="utf-8") as fh:
        ca = json.load(fh)
    print("已生成：%s" % out)
    print("  共用时间轴 %d 格 / 迁徙事件 %d 条 / 已接入 %d 姓 / 基底层 %d 点" % (
        len(ca["steps"]), len(ca["events"]), len(ca["surnames"]), len(load_places())))
    return out


def build_h5():
    """生成公众号 H5：index.html（单文件自包含，约 1 MB）。

    旧 5 期核查页不再占用 index.html，改由 build_check() 输出 atlas_check.html。
    H5 的数据来自 h5data/core.js（build_surname_list.py + build_h5_data.py 的产物），
    内嵌进页面，部署时只需上传一个 HTML；地图与微信分享配置在页面顶部
    window.__H5_CONFIG__ 里改，不需要重新构建。
    """
    if not H5_TEMPLATE_FILE.exists():
        print("  ⚠ 未找到 h5.template.html，跳过公众号 H5")
        return None
    if not H5_CORE_FILE.exists():
        raise SystemExit("缺少 %s，请先运行：python build_surname_list.py && python build_h5_data.py"
                         % H5_CORE_FILE)
    tpl = H5_TEMPLATE_FILE.read_text(encoding="utf-8")
    if H5_PLACEHOLDER not in tpl:
        raise SystemExit("H5 模板缺少占位符 %s" % H5_PLACEHOLDER)
    raw = H5_CORE_FILE.read_text(encoding="utf-8").strip()
    prefix = "window.__H5_CORE__="
    if not raw.startswith(prefix):
        raise SystemExit("h5data/core.js 格式异常，缺少 %s 前缀" % prefix)
    core_json = raw[len(prefix):].rstrip().rstrip(";").replace("</", "<\\/")
    html = tpl.replace(H5_PLACEHOLDER, core_json)
    out = ROOT / "index.html"
    out.write_text(html, encoding="utf-8")
    core = json.loads(H5_CORE_FILE.read_text(encoding="utf-8")[len(prefix):].rstrip().rstrip(";"))
    print("已生成：%s（公众号 H5，%.1f KB，单文件自包含）" % (out, out.stat().st_size / 1024))
    print("  可选姓氏 %d 个 / 逐姓史料 %d 个 / 共用时间轴 %d 格 / 迁徙事件 %d 条 / 点位库 %d 条"
          % (len(core["list"]), len(core["fullChars"]), len(core["steps"]),
             len(core["events"]), len(core["PL"])))
    return out


def select(data, key):
    """按汉字或 id 精确匹配一个姓氏；未命中则报错。"""
    if key is None:
        return data
    key = key.strip()
    hits = [s for s in data["surnames"] if s["char"] == key or s["id"] == key.lower()]
    if not hits:
        available = "、".join(s["char"] for s in data["surnames"])
        raise SystemExit("未找到姓氏 %r。当前可用：%s" % (key, available))
    subset = dict(data)
    subset["surnames"] = hits
    subset["meta"] = dict(data["meta"])
    subset["meta"]["sampleSize"] = len(hits)
    subset["meta"]["note"] = "单姓数据包，由 build.py --surname %s 生成。" % hits[0]["char"]
    return subset


def main():
    ap = argparse.ArgumentParser(description="构建姓氏地理热力交互页面")
    ap.add_argument("--surname", help="只输出指定姓氏（汉字或 id）")
    ap.add_argument("--out", help="输出文件名，默认 index.html；单姓模式默认 <姓>姓.html")
    ap.add_argument("--list", action="store_true", help="列出当前数据里的姓氏")
    ap.add_argument("--cinema", action="store_true", help="只生成 34 格纯可视化出片页 cinema.html")
    ap.add_argument("--h5", action="store_true", help="只生成公众号 H5 页面 index.html")
    ap.add_argument("--check", action="store_true", help="只生成旧 5 期史料核查页 atlas_check.html")
    args = ap.parse_args()

    if args.h5:
        build_h5()
        return
    if args.cinema:
        build_cinema()
        return

    data = load_data()

    if args.list:
        print("当前数据：%d 个姓氏" % len(data["surnames"]))
        for s in data["surnames"]:
            print("  %s (%s)  郡望：%s  断面：%d" % (
                s["char"], s["id"], s["origin"], len(s["timeline"])))
        print("历史断面：%d 期" % len(data["meta"]["periods"]))
        src = load_sources()
        print("可引用来源：%d 条 / 事实 %d 条（仅当代，见 sources.json）" % (
            len(src.get("sources", [])), len(src.get("facts", []))))
        ev = load_evidence()
        names = list(ev.get("surnames", {}).keys())
        print("可考记录证据层：已接入 %d 个姓（%s）" % (
            len(names), "、".join(names) if names else "暂无"))
        return

    payload = select(data, args.surname)
    out_name = args.out
    if not out_name:
        # index.html 已是公众号 H5，旧核查页另存，避免把两个页面混在一起
        out_name = (payload["surnames"][0]["char"] + "姓.html") if args.surname else "atlas_check.html"
    out_path = ROOT / out_name

    template = TEMPLATE_FILE.read_text(encoding="utf-8")
    missing = [p for p in (PLACEHOLDER, SOURCES_PLACEHOLDER, EVIDENCE_PLACEHOLDER,
                           PLACES_PLACEHOLDER, GENEALOGY_PLACEHOLDER)
               if p not in template]
    if missing:
        raise SystemExit("模板缺少占位符 %s，请检查 index.template.html" % "、".join(missing))

    sources = load_sources()
    evidence = load_evidence()
    places = load_places()
    genealogy = load_genealogy()
    html = template.replace(PLACEHOLDER, inline_json(payload))
    html = html.replace(SOURCES_PLACEHOLDER, inline_json(sources))
    html = html.replace(EVIDENCE_PLACEHOLDER, inline_json(evidence))
    html = html.replace(PLACES_PLACEHOLDER, inline_json(places))
    html = html.replace(GENEALOGY_PLACEHOLDER, inline_json(genealogy))

    # 单姓版本把标题与提示同步改掉
    if args.surname:
        ch = payload["surnames"][0]["char"]
        html = html.replace("百家姓地理繁衍 · 点密度样品（10 姓）", "百家姓地理繁衍 · %s姓单姓版" % ch)
        html = html.replace("样品覆盖 10 个大姓", "单姓版：%s" % ch)

    out_path.write_text(html, encoding="utf-8")
    print("已生成：%s" % out_path)
    print("  姓氏 %d 个 / 历史断面 %d 期 / 地名坐标 %d 条" % (
        len(payload["surnames"]), len(payload["meta"]["periods"]), len(payload["places"])))
    print("  可引用来源 %d 条 / 事实 %d 条（仅当代分布）" % (
        len(sources.get("sources", [])), len(sources.get("facts", []))))
    ev_names = list(evidence.get("surnames", {}).keys())
    ev_count = 0
    for ch in ev_names:
        for per in evidence["surnames"][ch].get("periods", {}).values():
            for pl in per.get("places", []):
                ev_count += len(pl.get("evidence", []))
    print("  可考记录证据层：已接入 %d 姓（%s）/ 共 %d 条证据 / %d 条数据补齐指引" % (
        len(ev_names), "、".join(ev_names) if ev_names else "暂无",
        ev_count, len(evidence.get("acquisition", []))))
    gen = genealogy.get("surnames", {})
    gen_names = list(gen.keys())
    gen_sites = sum(len(per.get("sites", []))
                    for c in gen.values() for per in c.get("periods", {}).values())
    print("  基底层：%d 个行政单元中心点（与姓无关，构成有人区骨架）" % len(places))
    print("  史料层：已接入 %d 姓（%s）/ 共 %d 处聚居地点记录" % (
        len(gen_names), "、".join(gen_names) if gen_names else "暂无", gen_sites))
    print("  渲染为确定性：同一姓氏同一断面，点密度点位与数量完全一致，便于后续逐帧导出。")

    if args.check:
        return
    # 顺带生成 34 格百年时间轴的纯可视化出片页（无口播、无字幕）
    print("")
    build_cinema()
    # 以及公众号 H5 自选姓氏页（index.html）
    print("")
    build_h5()


if __name__ == "__main__":
    main()
