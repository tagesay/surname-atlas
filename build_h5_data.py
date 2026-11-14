# -*- coding: utf-8 -*-
"""把 34 格百年序列编译成公众号 H5 用的轻量数据。

产物
----
  h5data/core.js         通用核心（时间轴 / 19 事件 / 3137 点位 / 672 姓清单 /
                         4 档通用 34 格骨架 / 官方省级结论）
  h5data/full/<姓>.js    10 个逐姓史料帧，选中该姓时按需注入
  h5data/_core.json      同一份核心的 JSON 形式，供校验与调试

设计要点（必须守住，否则就是拿通用骨架冒充逐姓史料）
--------------------------------------------------
1. 通用骨架不是新编的一套数据，而是从已出片的 century_atlas.json 里
   「剥掉逐姓史料」得到：只保留 source_ref 指向 migration_events.json 的
   事件走廊点，以及 sources.json 中 tierLevel=present/None 的近现代铺开点。
   逐姓的 research/*.json 锚点、发祥地、top/maxpop 省级结论一律剔除。
2. 4 档差异只来自「现代常见姓氏排名」这一公开名录，用确定性取样调整
   近现代省内铺开点的覆盖率；不按人口数加权、不伪造发祥地。
   D 档（只见于《百家姓》、未入现代 600 名）不铺开，页面会说明原因。
3. 4 条专属事件（陈/王/黄）只对命中姓显示，绝不套用到其他姓。
4. 帧用紧凑数组 [placeIdx, n*10, kindCode, tierCode]，place 的经纬度
   统一放 PL 数组，避免 34 格 × 数百点重复存字符串。
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "h5data"
FULL_DIR = OUT / "full"

LEVELS = {"province": 0, "city": 1, "county": 2, "district": 2}
TIERS = {"present": 0, "top": 1, "maxpop": 2}
# 4 档近现代铺开覆盖率，依据：现代常见姓氏排名 1—600 + 公安部「常见姓氏 31 省均有分布」
TIER_RATIO = {"A": 1.00, "B": 0.62, "C": 0.34, "D": 0.00}
TIER_LABEL = {
    "A": "现代常见姓氏前 100 名",
    "B": "现代常见姓氏 101—300 名",
    "C": "现代常见姓氏 301—600 名",
    "D": "《百家姓》收录、未列入现代常见 600 名",
}


def load(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def h01(s):
    return int(hashlib.md5(s.encode("utf-8")).hexdigest()[:8], 16) / 0xFFFFFFFF


def tier_of(rank, in_bjx):
    if rank is None:
        return "D"
    if rank <= 100:
        return "A"
    if rank <= 300:
        return "B"
    if rank <= 600:
        return "C"
    return "D"


def compact(fr, keep=None):
    out = []
    for s in fr.get("sites", []):
        pi = PLACE_IDX.get(s["place"])
        if pi is None:
            continue
        if keep is not None and not keep(s):
            continue
        kind = 1 if s.get("spread") else (2 if s.get("kind") == "fade" else 0)
        out.append([pi, int(round(float(s.get("n", 0)) * 10)),
                    kind, TIERS.get(s.get("tierLevel"), 0)])
    return out


def is_common(s):
    """是否属于「与姓无关、可共用」的点。"""
    ref = s.get("source_ref") or ""
    if ref.startswith("migration_events.json#"):
        return True
    if ref.startswith("sources.json#"):
        # top / maxpop 是「该姓为某省第一大姓 / 该姓人口最多省份」的逐姓结论，不能共用
        return s.get("tierLevel") in (None, "present")
    return False


def province_index(places):
    """省名 → 点位下标，兼容「河南 / 山东省 / 广西壮族自治区」等写法。"""
    idx = {}
    for k, p in places.items():
        if p.get("level") != "province":
            continue
        name = p["name"]
        keys = {name, re.sub(r"(省|市|自治区|特别行政区)$", "", name)}
        keys.add(re.sub(r"(维吾尔|壮族|回族)$", "", list(keys)[-1]))
        for kk in keys:
            idx.setdefault(kk, PLACE_IDX[k])
    return idx


def main():
    ca = load("century_atlas.json")
    places = load("places.json")
    events_doc = load("migration_events.json")
    surname_doc = load("surname_list.json")
    sources = load("sources.json")

    global PLACE_IDX
    pkeys = sorted(places.keys())
    PLACE_IDX = {k: i for i, k in enumerate(pkeys)}
    PL = []
    for k in pkeys:
        p = places[k]
        PL.append([round(float(p["lat"]), 4), round(float(p["lng"]), 4),
                   LEVELS.get(p.get("level"), 2)])

    steps = [{
        "id": s["id"], "label": s["label"], "era": s["era"],
        "dyn": s.get("dynasty", ""), "mode": s["mode"],
        "cs": s.get("centuryStart"), "ce": s.get("centuryEnd"),
    } for s in ca["steps"]]

    ev = {}
    for e in events_doc["events"]:
        ev[e["id"]] = {
            "id": e["id"], "n": e["name"], "s": e["start"], "e": e["end"],
            "t": e["tier"], "b": e.get("brief", ""), "src": e.get("source", ""),
            "sc": e.get("scope", "all"), "note": e.get("note", ""),
        }

    # ---- 通用骨架：以已出片的「李」帧为基底，剥掉逐姓史料 ----
    base = ca["surnames"]["李"]["frames"]
    generic = {}
    for t, ratio in TIER_RATIO.items():
        def keep(s, _t=t, _r=ratio):
            if not is_common(s):
                return False
            if s.get("spread") and s.get("event") == "ev_xiandai":
                return h01(_t + "|" + str(s["place"])) < _r
            return True
        generic[t] = [compact(base[i], keep) for i in range(len(steps))]

    # 共用事件清单：李姓帧里的事件全是 scope=all 的（李不命中陈/王/黄专属事件）
    common_events = [[e["id"] for e in base[i].get("events", [])]
                     for i in range(len(steps))]
    all_events = [list(x) for x in common_events]
    for i, e in enumerate(events_doc["events"]):
        sc = e.get("scope", "all")
        if sc == "all":
            continue
        for step_i, st in enumerate(steps):
            if st["mode"] != "century":
                continue
            c = st["cs"]
            if e["start"] <= c <= e["end"]:
                all_events[step_i].append(e["id"])

    # ---- 逐姓 full 帧 ----
    FULL_DIR.mkdir(parents=True, exist_ok=True)
    full_meta = {}
    full_frames = {}
    for ch, rec in ca["surnames"].items():
        frames = [compact(fr) for fr in rec["frames"]]
        full_frames[ch] = frames
        origins = rec.get("origin") or {}
        srcs = []
        for x in (rec.get("sources") or [])[:40]:
            if isinstance(x, dict):
                srcs.append(x.get("title") or x.get("name") or x.get("cite") or "")
            else:
                srcs.append(str(x))
        meta = {
            "char": ch,
            "origin": {
                "region": origins.get("modern_region", ""),
                "dynasty": origins.get("dynasty", ""),
                "basis": origins.get("basis", ""),
                "place": origins.get("place", ""),
                "firstStep": origins.get("firstStep"),
            },
            "sources": [s for s in srcs if s][:24],
            "events": [[e["id"] for e in fr.get("events", [])] for fr in rec["frames"]],
        }
        full_meta[ch] = meta
        js = ("window.__H5_FULL__=window.__H5_FULL__||{};"
              "window.__H5_FULL__[%s]={f:%s};"
              % (json.dumps(ch, ensure_ascii=False),
                 json.dumps(frames, separators=(",", ":"))))
        (FULL_DIR / (ch + ".js")).write_text(js, encoding="utf-8")

    # ---- 官方省级结论：人口最多省份 / 各省第一大姓 / 台湾前十大姓 ----
    pidx_prov = province_index(places)
    max_prov = {}
    for ch, prov in sources["maxProvince2021"]["bySurname"].items():
        key = re.sub(r"(省|市|自治区|特别行政区)$", "", prov)
        pi = pidx_prov.get(key) or pidx_prov.get(prov)
        if pi is not None:
            max_prov[ch] = pi
    top_prov = {}
    for ch, arr in sources["provinceTopSurname2019"]["bySurname"].items():
        got = []
        for prov in arr:
            key = re.sub(r"(省|市|自治区|特别行政区)$", "", prov)
            pi = pidx_prov.get(key) or pidx_prov.get(prov)
            if pi is not None and pi not in got:
                got.append(pi)
        if got:
            top_prov[ch] = got
    tw_top = [x["surname"] for x in sources["taiwan"].get("topSurnames", [])]
    tw_points = [PLACE_IDX[k] for k in pkeys
                 if places[k].get("level") in ("county", "province")
                 and (k.startswith("TW-") or places[k].get("path", "").startswith("台湾"))]

    core = {
        "v": "1.0.0",
        "brand": "TigerFRM",
        "steps": steps,
        "events": ev,
        "PL": PL,
        "pkeys": pkeys,
        "generic": generic,
        "tierRatio": TIER_RATIO,
        "tierLabel": TIER_LABEL,
        "commonEvents": common_events,
        "allEvents": all_events,
        "list": surname_doc["surnames"],
        "listMeta": surname_doc["meta"],
        "fullChars": sorted(ca["surnames"].keys()),
        "fullFrames": full_frames,
        "fullMeta": full_meta,
        "maxProv": max_prov,
        "topProv": top_prov,
        "twTop": tw_top,
        "twPoints": tw_points,
        "caveat": (
            "点数不是人口数。10 个带「史」标的姓使用逐姓史料帧；其余姓使用共用迁徙事件"
            "与现代常见姓氏分布骨架，不标专属发祥地、不伪造家谱出处。"
            "页面不画任何国界/省界/历史疆域，不做分省设色。"
        ),
    }

    # ---- 家谱/谱牒依据层：genealogy_batch1.json 接入专属帧 + 详情卡 + 角标 ----
    # 这些姓已有公开谱牒学依据（元和姓纂/通志/百家姓考略等），为其生成「锚点真实、
    # 点数示意」的专属帧与依据元数据；角标统一由 badgeMap 控制（史/官/家 并集）。
    badge_map = {}
    geo_surnames = []
    for _gp in ("genealogy_batch1.json", "genealogy_batch2.json", "genealogy_batch3.json", "genealogy_batch4.json", "genealogy_batch5.json", "genealogy_batch6.json", "genealogy_batch7.json"):
        _p = ROOT / _gp
        if _p.exists():
            _g = json.loads(_p.read_text(encoding="utf-8"))
            geo_surnames += [_r for _r in _g.get("surnames", []) if _r.get("c")]
        prov_idx = {}
        for code, p in places.items():
            if p.get("level") == "province":
                prov_idx.setdefault(p.get("name", ""), code)
        PROV_2 = ["北京","天津","上海","重庆","河北","山西","辽宁","吉林","黑龙江","江苏","浙江","安徽","福建","江西","山东","河南","湖北","湖南","广东","海南","四川","贵州","云南","陕西","甘肃","青海","台湾","内蒙古","广西","西藏","宁夏","新疆","香港","澳门"]
        def core_name(frag):
            frag = re.sub(r"(今|一带|附近|周边|境内|等地)$", "", frag).strip()
            frag = re.sub(r"^今", "", frag).strip()
            for p in PROV_2:
                if frag.startswith(p): frag = frag[len(p):]; break
            return frag
        def to_codes(m):
            out = []
            for frag in re.split(r"[／/、，,\s]+", m):
                core = core_name(frag)
                if not core: continue
                prov = None
                for p in PROV_2:
                    if core.startswith(p): prov = p; core = core[len(p):]; break
                hit = None
                for code, pl in places.items():
                    if pl.get("level") == "province": continue
                    path = pl.get("path") or pl.get("name") or ""
                    if prov and prov not in path: continue
                    nm = pl.get("name", "")
                    if nm == core or (nm.startswith(core) and len(nm) - len(core) <= 3):
                        hit = code; break
                if hit: out.append(hit)
                elif prov and prov in prov_idx: out.append(prov_idx[prov])
            return out
        def first_step(d):
            if any(k in d for k in ["夏","商","西周","春秋","战国","先秦"]): return 1
            if "秦" in d or "汉" in d: return 3
            if "魏晋" in d or "三国" in d: return 5
            if "唐" in d: return 10
            if "宋" in d: return 12
            if "元" in d: return 15
            if "明" in d: return 16
            if "清" in d: return 17
            return 2
        for rec in geo_surnames:
            ch = rec.get("c")
            if not ch: continue
            if ch in badge_map: continue   # 跨批次去重，避免重复接入专属帧
            if rec.get("note") and "待核" in rec["note"]: continue  # 待核姓暂不接入专属帧
            origin = rec.get("origin") or {}
            mods = origin.get("modern") or []          # 容错：允许 modern 为字符串
            if isinstance(mods, str): mods = [mods]
            codes = []
            for m in mods: codes += to_codes(m)
            codes = list(dict.fromkeys(codes))
            place_code = codes[0] if codes else None
            pi = PLACE_IDX.get(place_code) if place_code else None
            dyn = origin.get("dynasty", "") or ""
            fs = first_step(dyn)
            rank = None; bjx = None; old_lv = None
            for x in surname_doc["surnames"]:
                if x["c"] == ch: rank = x.get("rank"); bjx = x.get("bjx"); old_lv = x.get("lv"); break
            tier = tier_of(rank, bjx)
            fam_frames = []
            for step_i in range(len(steps)):
                base = [list(s) for s in generic[tier][step_i]]
                if pi is not None and step_i >= fs:              # 得姓地真实锚点（首现后持续）
                    base.append([pi, 20, 0, TIERS.get(tier, 0)])
                for ci in codes[1:]:                              # 其余郡望/发祥地锚点（稍后起始）
                    pii = PLACE_IDX.get(ci)
                    if pii is not None and step_i >= fs + 1:
                        base.append([pii, 18, 0, TIERS.get(tier, 0)])
                fam_frames.append(base)
            full_frames[ch] = fam_frames
            full_meta[ch] = {
                "char": ch,
                "origin": {"region": "、".join(origin.get("modern") or []), "dynasty": dyn,
                           "basis": origin.get("text", ""), "place": place_code or "", "firstStep": fs},
                "sources": [{"title": s.get("title",""), "author": s.get("author",""),
                             "type": s.get("type",""), "quote": s.get("quote","")}
                            for s in (rec.get("sources") or [])],
                "events": common_events,                          # 共用迁徙事件走廊
                "wang": origin.get("wang") or [],
                "migration": rec.get("migration", ""),
            }
            fam_js = ("window.__H5_FULL__=window.__H5_FULL__||{};"
                      "window.__H5_FULL__[%s]={f:%s};"
                      % (json.dumps(ch, ensure_ascii=False),
                         json.dumps(fam_frames, separators=(",", ":"))))
            (FULL_DIR / (ch + ".js")).write_text(fam_js, encoding="utf-8")
            parts = []
            if old_lv == "official": parts.append("官")            # 原有官方结论保留
            parts.append("家")                                     # 谱牒依据
            badge_map[ch] = "·".join(parts)
    for ch in ca["surnames"].keys():
        badge_map[ch] = "史"
    for x in surname_doc["surnames"]:
        if x.get("lv") == "official" and x["c"] not in badge_map:
            badge_map[x["c"]] = "官"
    core["badgeMap"] = badge_map

    OUT.mkdir(exist_ok=True)
    (OUT / "_core.json").write_text(
        json.dumps(core, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    js = ("window.__H5_CORE__=" +
          json.dumps(core, ensure_ascii=False, separators=(",", ":")) + ";")
    (OUT / "core.js").write_text(js, encoding="utf-8")

    sizes = ["%s %d 点" % (t, sum(len(f) for f in generic[t])) for t in TIER_RATIO]
    print("核心数据 %.1f KB / 点位库 %d 条 / 时间轴 %d 格 / 事件 %d 条 / 姓氏 %d 个"
          % ((OUT / "core.js").stat().st_size / 1024, len(PL), len(steps),
             len(ev), len(core["list"])))
    print("通用骨架：" + "；".join(sizes))
    _full_files = [FULL_DIR / (c + ".js") for c in full_meta
                   if (FULL_DIR / (c + ".js")).exists()]
    print("逐姓 full 帧：%d 个文件，合计 %.1f KB"
          % (len(_full_files), sum(p.stat().st_size for p in _full_files) / 1024))
    print("官方结论：人口最多省份 %d 姓 / 各省第一大姓 %d 姓 / 台湾前十大姓 %d 姓 / 台湾点位 %d"
          % (len(max_prov), len(top_prov), len(tw_top), len(tw_points)))
    # 一致性自检
    # 自检：专属事件只能在通用事件之外追加，不得丢失共用事件；
    # 且 4 条专属事件绝不能出现在 commonEvents 里（否则会套用到所有姓）。
    exclusive_ids = {e["id"] for e in events_doc["events"] if e.get("scope") != "all"}
    bad = [i for i in range(len(steps))
           if not set(common_events[i]).issubset(set(all_events[i]))]
    leaked = [eid for x in common_events for eid in x if eid in exclusive_ids]
    ok = (not bad) and (not leaked) and len(exclusive_ids) == 4
    print("自检：通用事件格 %d / 含专属事件格 %d / 专属事件 %d 条 / 校验 %s"
          % (sum(1 for x in common_events if x),
             sum(1 for i, x in enumerate(all_events) if len(x) > len(common_events[i])),
             len(exclusive_ids), "通过" if ok else "异常"))
    if not ok:
        print("  bad=%s leaked=%s" % (bad, leaked))
        return 1
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main())
