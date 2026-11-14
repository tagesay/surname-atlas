# -*- coding: utf-8 -*-
"""
近现代期密度模型：从「每省 1 个点」升级为「省内铺开 + 分级密度」。

问题背景
--------
公安部《二〇二一年全国姓名报告》的结论是「常见姓氏在全国 31 个省（区、市）均有分布」。
旧实现把这句话翻译成「每省落 1 个点、点数 1.0~3.2」。这对「全国都有」的大姓（如李，约占
全国人口 7.7%）是严重失真的：画面上只剩三十来个省级中心的小点，看不出这个姓在省内
究竟铺得多开，也看不出各省之间的强弱差别。

新模型
------
把「该姓在某省有分布」这句话展开到省级以下：
  · 该省的下辖地级市（直辖市为区、台湾为县市、香港澳门为区）全部落点；
  · 每一点的点数由「该姓在该省的证据强度」决定，三档：
      第一大姓  >  人口最多的省份  >  省内一般分布
    （依据：公安部 2019/2021 年全国姓名报告的官方归属表，逐条带 basis 与出处）
  · 省内若已有史料核实的更细地点（县级市、县），保留并单独计点，
    不被省级铺开吞掉。

为什么不做「按人口密度加权」
----------------------------
人口分布是受管控的专题信息，把省级人口数按比例摊到市县、再用点密度表达，
实质上就是一张未经审核的人口分布专题图。因此本模型**不使用任何人口数**：
铺开的理由是「该姓在该省确有分布」这一官方结论本身，
点的多少只表示「该姓在该省的证据强度与延续性」，不表示人口多少。

输出
----
在 genealogy.json 的每个姓的 modern 期里，除原有省级点外，增加省内铺开的市县点。
铺开的点带 `spread: true` 标记与统一 basis，页面据此区分「省级结论点」与「省内铺开点」。
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PLACES_FILE = ROOT / "places.json"

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# 省级铺开的粒度：直辖市/特别行政区到区级，省/自治区到地级市，台湾到县市
# 港澳台不参与「31 省均有分布」的结论，单独处理（见 compile_modern_sites）

# 证据强度三档 → 该省内每个铺开点的点数
TIER_POINTS = {
    "top": 2.2,        # 该姓为该省第一大姓（公安部 2019 年报告）
    "maxpop": 2.8,     # 该姓人口分布最多的省份（公安部 2021 年报告）
    "present": 1.15,   # 省内有分布记载（公安部 2021 年报告：31 省均有分布）
}

# 朝代 id → 中文标签，用于「延续」说明
PERIOD_LABEL = {
    "pre_qin": "先秦",
    "wei_jin": "两晋南北朝",
    "tang_song": "唐宋",
    "ming_qing": "明清",
    "modern": "近现代",
}

SPREAD_BASIS = {    "top": "公安部《二〇一九年全国姓名报告》：%s姓为%s第一大姓。省内按地级市展开，"
           "表示该姓在此省分布广、聚居点密集；展开为可视化刻度，非逐市统计。",
    "maxpop": "公安部《二〇二一年全国姓名报告》：%s姓人口分布最多的省份是%s。"
              "省内按地级市展开，表示该姓在此省聚居点最密；展开为可视化刻度，非逐市统计。",
    "present": "公安部《二〇二一年全国姓名报告》：常见姓氏在全国 31 个省（区、市）均有分布，"
               "%s姓在%s亦有分布。省内按地级市展开，表示分布到全省范围；"
               "展开为可视化刻度，非逐市统计。",
}


def load_places():
    with PLACES_FILE.open(encoding="utf-8") as f:
        return json.load(f)


def build_children(places):
    """adcode -> 其下级点位列表（含 level）。"""
    kids = defaultdict(list)
    for ad, p in places.items():
        if p.get("parent"):
            kids[p["parent"]].append(ad)
    return kids


def norm_province(s):
    """省级名称归一化：去掉「省/市/自治区/特别行政区」等后缀，用于比对官方名单。"""
    if not s:
        return ""
    s = re.sub(r"\s+", "", str(s))
    s = (s.replace("维吾尔", "").replace("壮族", "").replace("回族", "")
          .replace("特别行政区", "").replace("自治区", "").replace("省", ""))
    return s


def province_tier(surname, prov_ad, prov_name, by_adcode, by_name, max_prov):
    """判定某姓在某省的证据强度档位。返回 (tier, basis_kind)。"""
    name = prov_name
    nname = norm_province(name)
    is_top = False
    rec = by_adcode.get(prov_ad)
    if rec and rec.get("top") == surname:
        is_top = True
    else:
        for cand in (by_name.get(surname) or []):
            if norm_province(cand) == nname:
                is_top = True
                break
    if max_prov and norm_province(max_prov) == nname:
        # 人口最多的省份优先判为 maxpop（更强的特异性结论）
        return "maxpop", None
    if is_top:
        return "top", None
    return "present", None


def build_modern_spread(surname, places, kids, sources):
    """生成近现代期的「省级 + 省内铺开」站点。

    返回 (province_points, spread_points)
      province_points: 每个省一个锚点（保留原有省级落点语义）
      spread_points: 省内铺开的市县点
    """
    pst = sources.get("provinceTopSurname2019") or {}
    by_adcode = pst.get("byAdcode") or {}
    by_name = pst.get("bySurname") or {}
    max_prov = (sources.get("maxProvince2021") or {}).get("bySurname", {}).get(surname, "")

    province_points = []
    spread_points = []

    for ad, p in places.items():
        if p.get("level") != "province":
            continue
        pname = p["name"]

        # 港澳台不在公安部「31 个省（区、市）均有分布」口径内，单独列
        if ad == "710000":
            tier, _ = "present", None
        elif ad in ("810000", "820000"):
            tier = "present"
        else:
            tier, _ = province_tier(surname, ad, pname, by_adcode, by_name, max_prov)

        # 该省下辖市县：直辖市/特别行政区到区级，省/自治区到地级市，台湾到县市
        sub = [c for c in kids.get(ad, []) if places[c].get("level") in ("city", "district", "county")]
        sub.sort()

        province_points.append({
            "place": ad, "name": pname, "path": p.get("path", ""),
            "lat": p["lat"], "lng": p["lng"],
            "role": "有分布记载",
            "basis": SPREAD_BASIS[tier] % (surname, pname),
            "source_ids": [], "matchQuality": "province",
            "tier": tier, "n": TIER_POINTS[tier],
        })

        if not sub:
            continue
        # 省内铺开：每个市县落一点，点数按该省档位，再按「省内市县数量」轻微收敛，
        # 避免市县多的省份（广东21、重庆38）在视觉上压过市县少的省份。
        # 收敛系数只影响点的多少，不影响有无，故不涉及人口数。
        base = TIER_POINTS[tier]
        shrink = min(1.0, (14.0 / len(sub)) ** 0.28)
        n = round(base * shrink, 2)
        for c in sub:
            cp = places[c]
            spread_points.append({
                "place": c, "name": cp["name"], "path": cp.get("path", ""),
                "lat": cp["lat"], "lng": cp["lng"],
                "role": "有分布记载",
                "basis": SPREAD_BASIS[tier] % (surname, pname),
                "source_ids": [], "matchQuality": "modern_spread",
                "spread": True, "province": pname, "tier": tier,
                "n": n,
            })

    return province_points, spread_points


def main():
    places = load_places()
    kids = build_children(places)
    sources = json.loads((ROOT / "sources.json").read_text(encoding="utf-8"))
    g = json.loads((ROOT / "genealogy.json").read_text(encoding="utf-8"))

    total_prov = total_spread = 0
    for ch, c in g["surnames"].items():
        prov, spread = build_modern_spread(ch, places, kids, sources)
        per = c["periods"]["modern"]
        # 区分两类原有记录：
        #   · 旧的省级锚点（matchQuality='province'）→ 用新模型整体替换
        #   · 史料核实的更细地点（县级市、县、市辖区）→ 保留，并提升对应铺开点的点数与依据
        fine = [s for s in per["sites"] if s.get("matchQuality") not in ("province", "modern_spread")]

        # 历史聚居地的延续：发祥地、郡望、迁入地在近现代仍是该姓的聚居地，
        # 若不延续，这些点簇会在明清→近现代的切换中整簇消失，
        # 与「聚居地不会凭空消失」相矛盾，也会让史料点被铺开点淹没。
        carry = []
        for pid in ("pre_qin", "wei_jin", "tang_song", "ming_qing"):
            for s in (c["periods"].get(pid) or {}).get("sites", []):
                carry.append((pid, s))
        have_place = {s["place"] for s in fine}

        # 建立 place -> 铺开点 的索引，供史料细点"升级"用
        spread_by_place = {s["place"]: s for s in spread}
        merged_fine = []
        for s in fine:
            tgt = spread_by_place.get(s["place"])
            if tgt is None:
                # 该细点不在本轮铺开范围内（例如台湾省市县未铺开）→ 原样保留
                merged_fine.append(s)
                continue
            # 史料有更细的记载 → 用史料的依据与更高的点数覆盖铺开点
            tgt["basis"] = s.get("basis") or tgt["basis"]
            tgt["source_ids"] = s.get("source_ids") or []
            tgt["role"] = s.get("role") if s.get("role") in ("发祥地", "郡望", "迁入地", "有分布记载") else tgt["role"]
            tgt["n"] = round(max(tgt["n"], 3.0), 2)
            tgt["matchQuality"] = "modern_evidence"
            tgt["evidence"] = True

        # 历史聚居地点延续到近现代（未被铺开覆盖的才新增）
        for pid, s in carry:
            if s["place"] in have_place or s["place"] in spread_by_place:
                continue
            cs = dict(s)
            cs["basis"] = (s.get("basis") or "") + \
                " 该地点自" + PERIOD_LABEL.get(pid, pid) + "起即为该姓聚居地，近现代延续存在。"
            cs["matchQuality"] = "modern_carry"
            cs["evidence"] = True
            cs["carriedFrom"] = pid
            merged_fine.append(cs)
            have_place.add(s["place"])

        # 省级锚点 + 省内铺开（含被史料细点升级过的）+ 延续点
        per["sites"] = prov + spread + merged_fine
        per["label"] = "近现代"
        per["spreadNote"] = ("近现代期按「省级结论点 + 省内铺开点 + 史料细点」三层绘制；"
                              "省内铺开表示该姓在该省分布到全省范围，点数只表示证据强度，不是人口数。")
        total_prov += len(prov)
        total_spread += len(spread)
        n_ev = sum(1 for s in per["sites"] if s.get("evidence"))
        print("  %s：省级锚点 %d + 省内铺开 %d（其中 %d 处被史料细点升级）+ 额外史料点 %d = %d"
              % (ch, len(prov), len(spread), n_ev, len(merged_fine), len(per["sites"])))

    g["meta"]["modernSpreadModel"] = {
        "version": "2.0.0",
        "reason": "旧模型每省只落 1 点，无法表达大姓在省内的铺开程度，也无法区分各省强弱。",
        "tiers": {
            "maxpop": {"points": TIER_POINTS["maxpop"], "basis": "公安部《二〇二一年全国姓名报告》：该姓人口分布最多的省份"},
            "top": {"points": TIER_POINTS["top"], "basis": "公安部《二〇一九年全国姓名报告》：该姓为该省第一大姓"},
            "present": {"points": TIER_POINTS["present"], "basis": "公安部《二〇二一年全国姓名报告》：常见姓氏在 31 个省（区、市）均有分布"},
        },
        "noPopulationWeighting": "刻意不按人口密度加权：人口分布是受管控的专题信息，"
                                 "按人口摊点实质等于输出未经审核的人口分布专题图。"
                                 "铺开依据是「该姓在该省有分布」这一官方结论本身。",
        "pointSemantics": "点数 = 该姓在该地的证据强度（第一大姓 > 人口最多省 > 省内有分布）与延续性，不是人口数。",
    }

    (ROOT / "genealogy.json").write_text(
        json.dumps(g, ensure_ascii=False, indent=1), encoding="utf-8")
    print("genealogy.json 近现代密度模型已升级：省级锚点 %d + 省内铺开 %d" % (total_prov, total_spread))


if __name__ == "__main__":
    main()
