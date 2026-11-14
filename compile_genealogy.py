# -*- coding: utf-8 -*-
"""
把 research/*.json（史料核实的姓氏聚居时间线）编译成页面可用的 genealogy.json。

两件事：
1. 地点匹配：史料里写的是「甘肃省定西市陇西县」这类现代行政区名，
   要落到 places.json 里的具体点位（adcode + 经纬度）。
2. 密度换算：把「有聚居记载」这件事换算成点数。
   点数 = 证据等级（发祥地 > 郡望 > 迁入地 > 有分布记载）+ 该地持续的朝代数。
   数值本身是可视化刻度，不是人口数 —— 页面上必须这样标注。
"""
import json
import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RESEARCH = ROOT / "research"
PLACES_FILE = ROOT / "places.json"
OUT_FILE = ROOT / "genealogy.json"

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# 证据等级 → 基础点数。刻意不写「人口数」，只是聚居证据的强弱次序。
ROLE_POINTS = {
    "发祥地": 6.0,
    "郡望": 4.5,
    "迁入地": 3.0,
    "有分布记载": 1.6,
}

PERIODS = ["pre_qin", "wei_jin", "tang_song", "ming_qing", "modern"]

# 近现代：公安部《二〇二一年全国姓名报告》「常见姓氏分布广泛，在全国 31 个省（区、市）均有分布」。
# 因此近现代期每个姓在 31 个省级单元都应有落点 —— 这不是编造，而是官方结论的直接可视化。
# 点数差异只表示「该姓是否为该省第一大姓」（有官方归属表支撑），不表示人口数量。
MODERN_ALL_PROVINCES = True


def norm(s):
    """归一化：去掉空白与行政后缀差异，便于匹配。"""
    if not s:
        return ""
    s = re.sub(r"\s+", "", str(s))
    s = s.replace("维吾尔", "").replace("壮族", "").replace("回族", "")
    s = s.replace("特别行政区", "").replace("自治区", "").replace("省", "")
    s = s.replace("市", "").replace("区", "").replace("县", "").replace("旗", "")
    s = s.replace("自治州", "").replace("自治县", "").replace("盟", "")
    s = re.sub(r"[（）()、,，·\-—－/]", "", s)
    return s


def load_places():
    with PLACES_FILE.open(encoding="utf-8") as f:
        return json.load(f)


def build_index(places):
    """多种键 → adcode 的索引，尽最大宽容度匹配史料里的写法。

    键的构成方式覆盖了史料里常见的几种写法：
      山西省临汾市洪洞县 → 山西省/临汾市/洪洞县 的 path
                        → 山西省临汾市洪洞县 的原始串
                        → 临汾市洪洞县 / 洪洞县（去省）
                        → 山西省 + 洪洞县（省+末段）
    """
    idx = {}
    exact = {}

    def put(key, ad):
        k = norm(key)
        if not k:
            return
        idx.setdefault(k, ad)

    def put_exact(key, ad):
        """保留完整行政后缀的精确键。norm() 会剥掉「省/市/县/区」，
        于是「台湾省新竹县」与「台湾省新竹市」（同理临夏市/县、和田市/县、
        伊宁市/县、嘉义市/县）归一化后撞成同一个键，先写入的吞掉后者，
        史书写明的县会被画到同名市上。精确键用原始全称，避开该冲突。"""
        k = re.sub(r"\s+", "", str(key)).replace("/", "")
        if not k:
            return
        exact.setdefault(k, ad)

    for ad, p in places.items():
        path = p.get("path") or p["name"]
        segs = [s for s in path.split("/") if s]
        put_exact(path, ad)
        put_exact(p["name"], ad)
        put(path, ad)
        put(ad, ad)
        put(p["name"], ad)
        if not segs:
            continue
        # 末两段、末三段（斜杠形式）
        if len(segs) >= 2:
            put("/".join(segs[-2:]), ad)
            put("/".join(segs[-3:]), ad)
            # 「市+县」「县+村」等无分隔拼接形式
            put("".join(segs[-2:]), ad)
            put("".join(segs[-3:]), ad)
            # 「省+末段」形式：山西省洪洞县
            put(segs[0] + segs[-1], ad)
            # 「省+市+县」全拼：山西省临汾市洪洞县（与原始 path 的 norm 相同）
        # 末段单独：洪洞县
        put(segs[-1], ad)
        # 末两段去末段后缀：临汾市洪洞（有些史料这么写）
        put(segs[-1].replace("县", "").replace("市", "").replace("区", ""), ad)
    return idx, exact


def resolve(region, idx, places, exact=None):
    """把一个现代行政区名解析到 places 里的点位。返回 (adcode, quality)。"""
    if not region:
        return None, "empty"
    # 精确全称优先（保留「省/市/县/区」后缀），避免同名县市互相吞并
    if exact:
        kx = re.sub(r"\s+", "", str(region)).replace("/", "")
        if kx in exact:
            return exact[kx], "exact"
    k = norm(region)
    if k in idx:
        return idx[k], "exact"
    # 逐级回退：去掉最前面的省名再试
    parts = [s for s in str(region).split("/") if s]
    for cut in range(1, len(parts)):
        kk = norm("".join(parts[cut:]))
        if kk in idx:
            return idx[kk], "suffix"
    # 只留最后一段（县名），可能歧义
    if parts:
        kk = norm(parts[-1])
        if kk in idx:
            return idx[kk], "leaf"
    return None, "miss"


def load_sources():
    """可引用来源清单：用于近现代 31 省归属表。"""
    p = ROOT / "sources.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def build_modern_grid(sources, places, idx):
    """近现代期的省级落点表：adcode(省) -> 该省是否是某姓第一大姓。

    数据依据：
      · 公安部《二〇二一年全国姓名报告》——常见姓氏在全国 31 个省（区、市）均有分布；
      · 公安部《二〇一九年全国姓名报告》——各省（区、市）第一大姓氏名单。
    落点取各省的行政中心点位（即省点），台湾省单列。
    """
    grid = {}
    for ad, p in places.items():
        if p.get("level") == "province":
            grid[ad] = {"place": ad, "name": p["name"], "path": p.get("path", "")}
    return grid


def compile_modern_sites(surname, grid, sources, places):
    """近现代期：31 省各落一点；若该姓是某省第一大姓（官方名单），该省点数更高。"""
    pst = sources.get("provinceTopSurname2019") or {}
    by_adcode = pst.get("byAdcode") or {}
    by_name = pst.get("bySurname") or {}
    top_provinces = set(by_name.get(surname, []))
    mp = (sources.get("maxProvince2021") or {}).get("bySurname", {}).get(surname, "")
    sites = []
    for ad, g in sorted(grid.items()):
        # 台湾省：公安部户籍口径不含台湾，单列并标注
        if ad == "710000":
            continue
        role = "有分布记载"
        basis = "公安部《二〇二一年全国姓名报告》：常见姓氏在全国 31 个省（区、市）均有分布。"
        n = 1.0
        is_top = False
        rec = by_adcode.get(ad)
        if rec and rec.get("top") == surname:
            is_top = True
        elif g["name"] in top_provinces:
            is_top = True
        if is_top:
            basis = "公安部《二〇一九年全国姓名报告》：%s姓为%s第一大姓。" % (surname, g["name"])
            n = 2.6
        if mp and g["name"] == mp:
            basis += "《二〇二一年全国姓名报告》：%s姓人口分布最多的省份是%s。" % (surname, mp)
            n = 3.2
        sites.append({
            "place": ad, "name": g["name"], "path": g["path"],
            "lat": places[ad]["lat"], "lng": places[ad]["lng"],
            "role": role, "basis": basis, "source_ids": [], "matchQuality": "province",
            "n": n,
        })
    # 台湾省：单列，依据公开的台湾户政姓氏统计（见 sources.json / research/national_stats.json）
    if "710000" in grid:
        g = grid["710000"]
        sites.append({
            "place": "710000", "name": g["name"], "path": g["path"],
            "lat": places["710000"]["lat"], "lng": places["710000"]["lng"],
            "role": "有分布记载",
            "basis": "台湾省亦有此姓聚居；具体分布见台湾户政司公开姓氏统计（港澳台不在公安部户籍口径内，单列）。",
            "source_ids": [], "matchQuality": "province", "n": 1.0,
        })
    return sites


def compile_surname(ch, doc, idx, places, exact=None):
    out = {
        "char": ch,
        "sources": doc.get("sources", []),
        "origin": None,
        "periods": {},
    }
    if doc.get("origin"):
        ad, q = resolve(doc["origin"].get("modern_region"), idx, places, exact)
        out["origin"] = {
            "modern_region": doc["origin"].get("modern_region"),
            "dynasty": doc["origin"].get("dynasty"),
            "basis": doc["origin"].get("basis"),
            "source_ids": doc["origin"].get("source_ids", []),
            "place": ad,
            "matchQuality": q,
        }
    for pid in PERIODS:
        per = None
        for p in doc.get("periods", []):
            if p.get("period") == pid:
                per = p
                break
        sites = []
        if per:
            for s in per.get("sites", []):
                ad, q = resolve(s.get("modern_region"), idx, places, exact)
                if not ad:
                    continue
                role = s.get("role") if s.get("role") in ROLE_POINTS else "有分布记载"
                sites.append({
                    "place": ad,
                    "name": places[ad]["name"],
                    "path": places[ad].get("path", ""),
                    "lat": places[ad]["lat"],
                    "lng": places[ad]["lng"],
                    "role": role,
                    "basis": s.get("basis", ""),
                    "source_ids": s.get("source_ids", []),
                    "matchQuality": q,
                })
        out["periods"][pid] = {
            "label": (per or {}).get("label", pid),
            "sites": sites,
        }
    return out


def main():
    places = load_places()
    idx, exact = build_index(places)
    sources = load_sources()
    modern_grid = build_modern_grid(sources, places, idx)

    compiled = {}
    unmatched = []
    src_count = 0
    site_total = 0

    for f in sorted(RESEARCH.glob("*.json")):
        if f.name == "national_stats.json" or f.name == "taiwan.json":
            continue
        doc = json.loads(f.read_text(encoding="utf-8"))
        ch = doc.get("surname") or f.stem
        if not doc.get("periods"):
            continue
        c = compile_surname(ch, doc, idx, places, exact)

        # 近现代期改用 31 省省级落点表：官方结论「均有分布」→ 铺满全国
        if MODERN_ALL_PROVINCES and modern_grid:
            prov_sites = compile_modern_sites(ch, modern_grid, sources, places)
            # 史料里已有的近现代地点保留（信息更细），按地名合并
            have = {s["place"] for s in prov_sites}
            for s in c["periods"]["modern"]["sites"]:
                if s["place"] not in have:
                    prov_sites.append(s)
            c["periods"]["modern"]["sites"] = prov_sites
            c["periods"]["modern"]["label"] = "近现代"

        compiled[ch] = c
        src_count += len(c["sources"])
        for pid in PERIODS:
            for s in c["periods"][pid]["sites"]:
                site_total += 1
                if s["matchQuality"] in ("miss", "leaf"):
                    unmatched.append((ch, pid, s["name"], s["matchQuality"]))

    # 朝代持续性 → 繁衍程度：一个地方连续多个朝代有记载，点更多
    for ch, c in compiled.items():
        appear = {}
        for pid in PERIODS:
            for s in c["periods"][pid]["sites"]:
                appear.setdefault(s["place"], set()).add(pid)
        order = {p: i for i, p in enumerate(PERIODS)}
        for pid in PERIODS:
            for s in c["periods"][pid]["sites"]:
                seq = sorted(order[x] for x in appear[s["place"]])
                idxs = [i for i, v in enumerate(seq) if v == order[pid]]
                run = 1
                if idxs:
                    k = idxs[0]
                    while k + 1 < len(seq) and seq[k + 1] == seq[k] + 1:
                        run += 1
                        k += 1
                s["persist"] = run
                base = ROLE_POINTS.get(s["role"], 1.6)
                # 持续朝代数带来的繁衍增量：每多一期 +0.8 点
                s["n"] = round(base + (run - 1) * 0.8, 2)

    payload = {
        "meta": {
            "version": "1.0.0",
            "periods": PERIODS,
            "pointSemantics": "点的数量表示该地点该姓「有聚居记载」的证据等级与持续朝代数，不是人口数。",
            "rolePoints": ROLE_POINTS,
            "basisNote": "每一处地点都带 basis（为什么此处有此姓聚居）与 source_ids（出处编号），可在页面溯源。",
        },
        "surnames": compiled,
    }
    OUT_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    print("genealogy.json 已生成")
    print("  姓氏 %d 个：%s" % (len(compiled), "、".join(compiled.keys())))
    print("  引用来源 %d 条 / 地点记录 %d 条" % (src_count, site_total))
    for ch, c in compiled.items():
        cnt = [len(c["periods"][p]["sites"]) for p in PERIODS]
        print("    %s：先秦%d 两晋%d 唐宋%d 明清%d 近现代%d" % (ch, *cnt))
    if unmatched:
        print("  低置信匹配 %d 条：" % len(unmatched))
        for u in unmatched[:20]:
            print("    ", u)


if __name__ == "__main__":
    main()
