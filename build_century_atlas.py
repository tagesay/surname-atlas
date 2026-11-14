# -*- coding: utf-8 -*-
"""
把 research/*.json（史料锚点）+ timeline.json（34 格）+ migration_events.json（事件年表）
+ genealogy.json（近现代省内铺开模型）编译成 century_atlas.json。

设计要点
--------
1. 共用时间轴：34 格。早期 3 格粗步长只标起源传说，百年格 31 格。
2. 每个史料锚点绑定「首现世纪」：
     pre_qin   → 西周分封格（e2），先秦传说部分归 e0/e1
     wei_jin   → 4 世纪（永嘉之乱）
     tang_song → 7~10 世纪（按事件或期中值）
     ming_qing → 14~18 世纪（按事件或期中值）
     modern    → 20 世纪
   首现之后「延续」，每过一个世纪点密度按繁衍刻度递增；
   若该姓在后世不再有该地记载且不属长期郡望，则逐格衰减（凋零）。
3. 事件窗口：事件在 start→end 世纪内逐格给迁入地加点（事件级依据），
   而不是一次性冒出。走西口、闯关东、湖广填四川因此自然读得出来。
4. 近现代（20/21 世纪）：沿用 genealogy.json 的「省级锚点 + 省内铺开 + 史料细点 + 延续」三层模型。
5. 每个点带 basis / source_ids / event / tier / firstStep / age（延续了几格）。
   事件级依据：一条出处覆盖该事件带出的一组县，不伪造每点独立出处。

绝不做的事
----------
· 不编造史料：没有锚点也没有事件的格子，该地就是没有点。
· 不按人口密度加权：那等于输出未经审核的人口分布专题图。
· 不画任何边界线、不做分省设色。
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(ROOT))
from compile_genealogy import (ROLE_POINTS, build_index, resolve, load_places)

OUT = ROOT / "century_atlas.json"

# 史料五期 → 首现世纪。取「该期史料实际指向的年代」，不是期中值硬套。
PERIOD_FIRST_CENTURY = {
    "pre_qin": -11,      # 西周分封，以国为氏（多数大姓可考发源地自此）
    "wei_jin": 4,        # 永嘉之乱 311，衣冠南渡
    "tang_song": 8,      # 安史之乱 755 起南迁深入；开漳 669 等由事件另行提前
    "ming_qing": 14,     # 元末明初、洪武大移民
    "modern": 20,        # 近现代 31 省均有分布
}

# 事件 id → 首现世纪（用于把带 event 标记的史料点提前到事件发生的世纪）
def event_first_century(events):
    return {e["id"]: e["start"] for e in events}

# 繁衍刻度：每延续一格，点数增量。刻意不用人口数。
GROW_PER_STEP = 0.28
MAX_POINTS = 7.0
# 衰减：连续 N 格无新记载且非郡望/发祥地，则开始逐格变疏
FADE_AFTER = 6
FADE_PER_STEP = 0.35


def century_to_step(steps, c):
    """世纪 → 时间轴格索引。粗步长格按其覆盖区间匹配。"""
    for i, s in enumerate(steps):
        if s["mode"] == "origin":
            if s["centuryStart"] >= c >= s["centuryEnd"]:
                return i
        elif s["centuryStart"] <= c <= s["centuryEnd"]:
            return i
    # 找最接近的
    best, bd = 0, 999
    for i, s in enumerate(steps):
        d = min(abs(s["centuryStart"] - c), abs(s["centuryEnd"] - c))
        if d < bd:
            best, bd = i, d
    return best


def main():
    places = load_places()
    idx, exact = build_index(places)
    timeline = json.loads((ROOT / "timeline.json").read_text(encoding="utf-8"))
    steps = timeline["steps"]
    events_doc = json.loads((ROOT / "migration_events.json").read_text(encoding="utf-8"))
    events = events_doc["events"]
    ev_first = event_first_century(events)
    genealogy = json.loads((ROOT / "genealogy.json").read_text(encoding="utf-8"))

    # 事件地名预解析
    ev_resolved = {}
    for e in events:
        rec = {"from": [], "to": []}
        for field in ("from", "to"):
            for r in e[field]:
                ad, q = resolve(r, idx, places, exact)
                if ad:
                    rec[field].append(ad)
        ev_resolved[e["id"]] = rec

    out_surnames = {}
    for f in sorted((ROOT / "research").glob("*.json")):
        if f.name in ("national_stats.json", "taiwan.json"):
            continue
        doc = json.loads(f.read_text(encoding="utf-8"))
        ch = doc["surname"]
        sources = {s["id"]: s for s in doc.get("sources", [])}

        # ---- 1. 史料锚点：place -> {firstStep, role, basis, source_ids, event, tier} ----
        anchors = {}
        for period in doc.get("periods", []):
            pid = period["period"]
            base_c = PERIOD_FIRST_CENTURY[pid]
            for s in period.get("sites", []):
                ad, q = resolve(s["modern_region"], idx, places, exact)
                if not ad:
                    continue
                ev = s.get("event")
                c = ev_first.get(ev, base_c) if ev else base_c
                si = century_to_step(steps, c)
                role = s.get("role", "有分布记载")
                prev = anchors.get(ad)
                # 同一地点多次出现：取最早首现，保留更强角色与更细依据
                if prev is None or si < prev["firstStep"]:
                    anchors[ad] = {
                        "firstStep": si, "role": role,
                        "basis": s.get("basis", ""),
                        "source_ids": s.get("source_ids", []),
                        "source_ref": "research/%s.json#sources" % ch,
                        "event": ev, "tier": infer_tier(sources, s.get("source_ids", [])),
                        "originPeriod": pid,
                    }
                elif prev and ROLE_POINTS.get(role, 0) > ROLE_POINTS.get(prev["role"], 0):
                    prev["role"] = role
                    prev["basis"] = s.get("basis", prev["basis"])
                    prev["source_ids"] = s.get("source_ids", prev["source_ids"])

        # 发祥地：最早起源的姓，在早期粗步长格给一个淡点（明确标传说/后世追述）
        origin_c = None
        if doc.get("origin"):
            o = doc["origin"]
            oad, oq = resolve(o["modern_region"], idx, places, exact)
            if oad:
                # 传说类（上古/夏商）→ e0；西周 → e2
                dyn = o.get("dynasty", "")
                oc = -21 if any(k in dyn for k in ("上古", "传说", "黄帝", "夏商", "夏")) else \
                     -16 if "商" in dyn else \
                     -11 if any(k in dyn for k in ("西周", "周", "先秦", "东周")) else \
                     PERIOD_FIRST_CENTURY["pre_qin"]
                osi = century_to_step(steps, oc)
                origin_c = (oad, osi, o)

        # ---- 2. 逐格生成点位状态 ----
        frames = []
        # 活跃锚点：place -> 已延续格数、当前点数
        live = {}
        origin_ad = origin_c[0] if origin_c else None
        for si, st in enumerate(steps):
            sites = []
            mode = st["mode"]
            c = st["centuryStart"]
            active_events = []

            # (a) 起源示意格：只画发祥地淡点，明确标为传说/后世追述。
            #     注意：粗步长格也照常跑下面的 (b)(e)，否则先秦得姓/郡望锚点
            #     会首现在 e2 却因「origin 格直接 continue」而整批丢失。
            if mode == "origin" and origin_c and si >= origin_c[1]:
                oad, osi, o = origin_c
                p = places[oad]
                age = si - osi
                sites.append({
                    "place": oad, "name": p["name"], "path": p.get("path", ""),
                    "lat": p["lat"], "lng": p["lng"],
                    "n": round(min(2.0, 1.1 + age * 0.3), 2),
                    "role": "发祥地（传说）", "basis": o.get("basis", ""),
                    "source_ids": o.get("source_ids", []),
                    "event": None, "tier": "传说/后世追述",
                    "firstStep": osi, "age": age, "kind": "origin",
                    "spread": False, "evidence": True,
                })

            # (b) 该格新首现的史料锚点（含 e2 分封格）
            for ad, a in anchors.items():
                if a["firstStep"] == si:
                    live[ad] = {"age": 0, "anchor": a, "role": a["role"]}

            # (c) 事件窗口：在本格内的事件给迁入地加点（仅百年格）
            if mode == "century":
                for e in events:
                    if e["tier"] == "C":
                        continue  # C 级只作背景，不驱动点位
                    if not (e["start"] <= c <= e["end"]):
                        continue
                    if e["scope"] != "all" and ch not in e["scope"]:
                        continue
                    active_events.append(e)
                    for ad in ev_resolved[e["id"]]["to"]:
                        if ad in live:
                            # 已有锚点：事件给一次繁衍加速
                            live[ad]["boost"] = live[ad].get("boost", 0) + 0.55
                            continue
                        live[ad] = {
                            "age": 0,
                            "anchor": {
                                "firstStep": si, "role": "迁入地",
                                "basis": "%s。%s" % (e["name"], e["source"]),
                            "source_ids": [], "event": e["id"], "tier": e["tier"],
                            "eventName": e["name"],
                            "source_ref": "migration_events.json#" + e["id"],
                            "originPeriod": "event",
                            },
                            "role": "迁入地", "event": e,
                        }

            # (d) 近现代：叠加省内铺开三层模型（20/21 世纪）
            if mode == "century" and c >= 20 and ch in genealogy["surnames"]:
                gm = genealogy["surnames"][ch]["periods"]["modern"]["sites"]
                for s in gm:
                    ad = s["place"]
                    if s.get("spread") and not s.get("evidence"):
                        # 铺开点：单独一类，不进 live 繁衍逻辑
                        sites.append({
                            "place": ad, "name": s["name"], "path": s.get("path", ""),
                            "lat": s["lat"], "lng": s["lng"],
                            "n": s.get("n", 1.0),
                            "role": s.get("role", "有分布记载"),
                            "basis": s.get("basis", ""),
                            "source_ids": s.get("source_ids", []),
                            "event": "ev_xiandai", "tier": "A",
                            "eventName": "近现代 · 常见姓氏 31 省均有分布",
                            "source_ref": "sources.json#公安部2021全国姓名报告",
                            "firstStep": si, "age": 0, "kind": "spread",
                            "spread": True, "evidence": False,
                            "province": s.get("province"), "tierLevel": s.get("tier"),
                        })
                    elif ad not in live:
                        live[ad] = {
                            "age": 0,
                            "anchor": {
                                "firstStep": si, "role": s.get("role", "有分布记载"),
                                "basis": s.get("basis", ""),
                                "source_ids": s.get("source_ids", []),
                                "event": "ev_xiandai", "tier": "A",
                                "eventName": "近现代 · 常见姓氏 31 省均有分布",
                                "source_ref": "sources.json#公安部2021全国姓名报告",
                                "originPeriod": "modern",
                            },
                            "role": s.get("role", "有分布记载"),
                        }

            # (e) 活跃锚点逐格繁衍 / 凋零
            for ad, L in live.items():
                a = L["anchor"]
                p = places.get(ad)
                if not p:
                    continue
                if mode == "origin" and ad == origin_ad:
                    L["age"] += 1
                    continue  # 与传说发祥地淡点同位，不重复画
                age = L["age"]
                base = ROLE_POINTS.get(a.get("role"), 1.6)
                n = base + age * GROW_PER_STEP + L.get("boost", 0)
                L["boost"] = 0
                # 长期无新记载且非发祥地/郡望 → 凋零
                is_core = a.get("role") in ("发祥地", "郡望")
                if not is_core and age > FADE_AFTER and c < 20:
                    n -= (age - FADE_AFTER) * FADE_PER_STEP
                n = round(max(0.25, min(MAX_POINTS, n)), 2)
                if mode == "origin":
                    # 起源示意期刻意压低密度：此时只有得姓传说，不该满屏点
                    n = round(max(0.3, min(2.2, n * 0.4)), 2)
                kind = "fresh" if age == 0 else ("fade" if not is_core and age > FADE_AFTER + 4 else "live")
                sites.append({
                    "place": ad, "name": p["name"], "path": p.get("path", ""),
                    "lat": p["lat"], "lng": p["lng"],
                    "n": n, "role": a.get("role", "有分布记载"),
                    "basis": a.get("basis", ""),
                    "source_ids": a.get("source_ids", []),
                    "source_ref": a.get("source_ref"),
                    "event": a.get("event"), "tier": a.get("tier", "B"),
                    "eventName": a.get("eventName"), "source_ref": a.get("source_ref"),
                    "firstStep": a.get("firstStep", si), "age": age,
                    "kind": kind, "spread": False, "evidence": True,
                })
                L["age"] += 1

            frames.append({
                "step": si,
                "events": [{"id": e["id"], "name": e["name"], "tier": e["tier"]}
                           for e in active_events],
                "sites": sites,
            })

        out_surnames[ch] = {
            "char": ch,
            "sources": doc.get("sources", []),
            "origin": ({
                "modern_region": origin_c[2].get("modern_region"),
                "dynasty": origin_c[2].get("dynasty"),
                "basis": origin_c[2].get("basis"),
                "source_ids": origin_c[2].get("source_ids", []),
                "place": origin_c[0],
                "firstStep": origin_c[1],
            } if origin_c else None),
            "frames": frames,
        }

    payload = {
        "meta": {
            "version": "2.0.0",
            "timeline": {"count": len(steps), "source": "timeline.json"},
            "pointSemantics": "点数 = 该地该姓聚居证据强度 + 延续世纪数，不是人口数。",
            "growth": "每延续一格 +%.2f 点；连续 %d 格无新记载且非发祥地/郡望则逐格衰减。" %
                      (GROW_PER_STEP, FADE_AFTER),
            "eventDriven": "事件在起止世纪窗口内逐格给迁入地加点，走西口/闯关东/湖广填四川由此自然显现。",
            "noPopulationWeighting": "刻意不按人口密度加权，避免输出未经审核的人口分布专题图。",
            "granularity": "史料锚点落县级；迁徙走廊与省内铺开用地级市；官方宏观结论落省级。",
            "evidenceTiers": {"A": "正史/官方统计", "B": "地方志/族谱", "C": "学界通行说法（只作背景）"},
            "compliance": "不画任何国界/省界/历史疆域轮廓，不做分省设色，只用离散点密度。",
            "standard": {
                "confirmedOn": "2026-11-13",
                "confirmedBy": "用户确认后开工（使用前已打招呼）",
                "timeline": "所有姓共用 34 格时间轴：西周分封以前 3 格粗步长只做起源示意（标为传说/后世追述），分封之后从前 10 世纪起每 100 年一格直到 21 世纪（截 2026）。起点留给最早得姓的姓，其余姓在各自首现格之后才出现。",
                "granularity": "三层混合：① 史料锚点（发祥地/郡望/迁入地）落县级；② 迁徙走廊与省内铺开用地级市；③ 官方宏观结论（31 省均有分布）落省级。家谱中的乡名归并到所属县，原名保留在 basis，不单独标点。DataV 乡镇级接口实测 404，故不采用乡镇级标点。",
                "evidence": "事件级依据：一条迁徙事件的出处覆盖它带出的一组县，每个点仍标事件名与出处编号，不伪造逐点独立出处。A 正史/官方统计/政府发布；B 地方志/族谱/政府史志；C 学界通行说法只作背景，不单独驱动点位。走廊点位只表示事件波及范围，不表示逐市有独立记载。",
                "corridor": "走西口、闯关东、湖广填四川等大迁徙按 start→end 世纪窗口逐格给迁入地增加点密度，而非一次性冒出。",
                "noPopulationWeighting": "刻意不按人口密度加权；点数不是人口数，只表示聚居证据强度与延续世纪数。",
                "presentation": "本项目为姓氏繁衍的纯可视化，没有口播、没有解说字幕。画面只有姓氏字标、年代刻度、离散点与右下角的迁徙事件标注；底部 34 格进度条按用户 2026-11-13 要求已取消。",
                "eventAnnotation": "右下角事件标注显示该世纪全部活跃事件，全部展示、不折叠、不出现「另有 N 条」（用户 2026-11-13 明确要求）；A 级（正史/官方）优先排序。每条显示事件名、起止世纪、依据等级、1~2 句背景简介。简介来自 migration_events.json 的 brief 字段，只写「为什么会发生这次迁徙」，不是口播文案。无事件的世纪不显示，保持画面干净。视频在有事件的世纪额外停留，便于阅读。",
                "genealogyUsage": "族谱/宗谱用作事件级依据：确认某族某时自某地迁往某地，落点到所属县市，乡名归并到县并保留在 basis 文本里；不把家谱世系逐代换算成人口或点密度，也未做逐部家谱全文比对。",
                "bgm": "用户 2026-11-13 指定《Victory》；音频文件需由用户提供，用 add_bgm.py 在视频流不重编码的前提下合流（淡入 2.5 秒 / 淡出 3 秒 / 音量 0.30）。",
            },
        },
        "steps": steps,
        "events": events,
        "surnames": out_surnames,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    print("century_atlas.json 已生成")
    print("  时间轴 %d 格 / 事件 %d 条 / 已接入 %d 姓：%s" %
          (len(steps), len(events), len(out_surnames), "、".join(out_surnames)))
    for ch, c in out_surnames.items():
        ns = [len(f["sites"]) for f in c["frames"]]
        print("    %s：首格 %d / 末格 %d / 峰值 %d" % (ch, ns[0], ns[-1], max(ns)))


def infer_tier(sources, ids):
    """从该点引用的来源推断证据等级；无引用则按事件级依据记 B。"""
    best = "B"
    for i in ids:
        s = sources.get(i)
        if not s:
            continue
        t = s.get("tier", "")
        if t.startswith("A") or "官方" in t or "政府" in t or "统计局" in t:
            best = "A"
        elif t.startswith("C") and best != "A":
            best = "C"
    return best


if __name__ == "__main__":
    main()
