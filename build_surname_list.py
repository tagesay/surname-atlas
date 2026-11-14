# -*- coding: utf-8 -*-
"""生成全量姓氏清单 surname_list.json。

数据来源（均为可复核的公开名录 / 官方结论，不生成任何臆造姓氏）：
  1. 《百家姓》全文带拼音（baijiaxing.wjccx.com）：503 姓 = 442 单姓 + 61 复姓。
     页面自身明确说明「百家姓终」是结束词，不是 4 个姓；504 姓说法为误。
  2. 现代常见姓氏排名 1-600（baijiaxing.hao86.com 首页排名表），带拼音。
  3. sources.json：公安部《全国姓名报告》系列衍生的省级结论
     （各省第一大姓 / 某姓人口最多省份 / 分省公开人数 / 台湾前十大姓）。

合并口径：以「姓」字符串为键取并集。同时出现在两个名录里只保留一条，
但分别记下 bjx（百家姓序位）与 rank（现代排名）。

level 语义（前端必须如实展示，不得把通用骨架伪装成逐姓史料）：
  full     10 个姓，research/*.json 逐姓史料 + century_atlas.json 34 格专属帧
  official 有公安部系列省级结论，可用真实的「人口最多省份 / 第一大姓」标注
  generic  只有名录出处，无逐姓地理史料；演示用共用事件骨架，不标专属发祥地
"""
import json
import re
import ssl
import sys
import urllib.request
from collections import OrderedDict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CACHE = {
    "bjx": ROOT / "_probe_bjx.html",
    "hao": ROOT / "_probe_hao.html",
}
URL = {
    "bjx": "https://baijiaxing.wjccx.com/",
    "hao": "https://baijiaxing.hao86.com/",
}
OUT = ROOT / "surname_list.json"


def fetch(key):
    p = CACHE[key]
    if p.exists() and p.stat().st_size > 10000:
        return p.read_text(encoding="utf-8", errors="ignore")
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(URL[key], headers={"User-Agent": "Mozilla/5.0"})
    raw = urllib.request.urlopen(req, timeout=20, context=ctx).read()
    txt = raw.decode("utf-8", "ignore")
    p.write_text(txt, encoding="utf-8")
    return txt


def strip_tone(py):
    """带调拼音 → 无调 ASCII，用于搜索键。"""
    tones = "āáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜüńňǹêḿ"
    plain = ("aaaa" + "eeee" + "iiii" + "oooo" + "uuuu"
             + "vvvv" + "v" + "nnn" + "e" + "m")
    assert len(tones) == len(plain), (len(tones), len(plain))
    table = str.maketrans(tones, plain)
    s = str(py or "").lower().strip().translate(table)
    return re.sub(r"[^a-z]", "", s)


def parse_baijiaxing(html):
    """返回 [(姓, 拼音, 是否复姓)]，按《百家姓》原文顺序。"""
    m = re.search(r"<div class=['\"]bjx content['\"]>(.*?)</div>", html, re.S)
    body = m.group(1) if m else html
    # 单姓与复姓都在 <a class='bjx_a1...'> 里；结束词是 <span class='bjx_abg'>，不含 <a>。
    items = re.findall(
        r"<a href='[^']+' class='bjx_a1[^']*'><em>([^<]*)</em><strong>([^<]*)</strong></a>",
        body,
    )
    out = []
    for py, ch in items:
        ch = ch.strip()
        if not ch or not re.fullmatch(r"[\u3400-\u9fff]+", ch):
            continue
        out.append((ch, strip_tone(py), len(ch) > 1))
    return out


def parse_rank(html):
    """返回 [(姓, 拼音, 名次)]，现代常见姓氏排名 1-600。"""
    items = re.findall(
        r"<li><span[^>]*>排名：\s*(\d+)\s*</span><em>([^<]*)</em>"
        r"<a[^>]*href=['\"][^'\"]*['\"][^>]*>([^<]+)</a></li>",
        html,
    )
    out = []
    for rank, py, ch in items:
        ch = ch.strip()
        if not ch or not re.fullmatch(r"[\u3400-\u9fff]+", ch):
            continue
        out.append((ch, strip_tone(py), int(rank)))
    return out


def official_evidence():
    """把 sources.json 里的省级结论摊成 姓 -> 标签列表。"""
    src = json.loads((ROOT / "sources.json").read_text(encoding="utf-8"))
    ev = {}

    def add(ch, tag):
        ev.setdefault(ch, [])
        if tag not in ev[ch]:
            ev[ch].append(tag)

    for ch, provinces in src["provinceTopSurname2019"]["bySurname"].items():
        # 同一省份在两套来源里带 / 不带「省」后缀，去重后只做归属展示
        seen = []
        for p in provinces:
            base = re.sub(r"(省|市|自治区|特别行政区)$", "", p)
            key = re.sub(r"(维吾尔|壮族|回族|特别行政区)$", "", base)
            if key not in [x[0] for x in seen]:
                seen.append((key, p))
        add(ch, "top:" + "/".join(k for k, _ in seen[:8]))

    for ch, prov in src["maxProvince2021"]["bySurname"].items():
        add(ch, "max:" + prov)

    for rec in src.get("provinceSurnameCounts", []):
        ch = rec.get("surname", "")
        if len(ch) == 1:
            add(ch, "cnt:" + rec.get("province", ""))

    for i, rec in enumerate(src["taiwan"].get("topSurnames", []), 1):
        add(rec.get("surname", ""), "tw:" + str(i))

    return ev, src


def main():
    bjx = parse_baijiaxing(fetch("bjx"))
    ranks = parse_rank(fetch("hao"))
    singles = [x for x in bjx if not x[2]]
    compounds = [x for x in bjx if x[2]]
    print("《百家姓》解析：%d 姓（单姓 %d / 复姓 %d）" % (len(bjx), len(singles), len(compounds)))
    print("现代排名解析：%d 姓（名次 %d—%d）" % (len(ranks), ranks[0][2], ranks[-1][2]))

    if len(bjx) != 503 or len(compounds) != 61:
        print("！《百家姓》条目数与页面声明的 503/61 不符，请复核解析规则")
    if len(ranks) != 600:
        print("！现代排名不足 600 条，请复核解析规则")

    ev, src = official_evidence()
    full = set("王李张刘陈杨黄赵周吴")

    rows = OrderedDict()

    def slot(ch, py=None, bjx_order=None, rank=None, compound=None):
        if ch not in rows:
            rows[ch] = {
                "c": ch,
                "py": py or "",
                "ini": "",
                "cmp": bool(compound) if compound is not None else len(ch) > 1,
                "bjx": bjx_order,
                "rank": rank,
                "lv": "generic",
                "ev": [],
            }
        r = rows[ch]
        if py and not r["py"]:
            r["py"] = py
        if bjx_order is not None:
            r["bjx"] = bjx_order
        if rank is not None:
            r["rank"] = rank
        if compound is not None:
            r["cmp"] = bool(compound)
        return r

    for i, (ch, py, cmp_) in enumerate(bjx, 1):
        slot(ch, py, i, None, cmp_)
    for ch, py, rank in ranks:
        slot(ch, py, None, rank, len(ch) > 1)

    # 拼音兜底：只用已抓到的拼音，不臆造读音；确实缺失的留空并标 noPinyin
    try:
        from pypinyin import lazy_pinyin
        have_pinyin = True
    except ImportError:
        have_pinyin = False
    fallback = 0
    for ch, r in rows.items():
        if not r["py"] and have_pinyin:
            r["py"] = "".join(lazy_pinyin(ch))
            fallback += 1
        r["ini"] = r["py"][:1]
        r["ev"] = ev.get(ch, [])
        if ch in full:
            r["lv"] = "full"
        elif r["ev"]:
            r["lv"] = "official"

    data = {
        "meta": {
            "version": "1.0.0",
            "generatedOn": date.today().isoformat(),
            "total": len(rows),
            "sources": [
                {"id": "baijiaxing", "name": "《百家姓》全文带拼音（503 姓）",
                 "url": URL["bjx"], "note": "442 单姓 + 61 复姓；「百家姓终」为结束词，不计入姓氏。"},
                {"id": "rank600", "name": "现代常见姓氏排名 1—600",
                 "url": URL["hao"], "note": "网站自列排名，用于检索热度，不作人口数据使用。"},
                {"id": "mps", "name": "公安部《全国姓名报告》系列省级结论",
                 "url": "sources.json", "note": "只含归属判断，不含分省人口密度。"},
                {"id": "tw", "name": "台湾省内政部户政司《全国姓名统计分析》",
                 "url": "sources.json#taiwan", "note": "与大陆户籍口径不同，单列展示。"},
            ],
            "coverage": "以《百家姓》全文 503 姓与现代常见姓氏 1—600 名取并集，"
                        "覆盖常见单姓与多数通行复姓；不声称覆盖全部现存姓氏"
                        "（《中华姓氏大辞典》等收录的万余姓中大量为极罕见姓、"
                        "少数民族姓的汉字转写，无公开地理分布依据，不编造清单）。",
            "levelSemantics": {
                "full": "10 姓：research/*.json 逐姓史料 + century_atlas.json 的 34 格专属帧，"
                        "发祥地 / 郡望 / 族谱方志聚居点可逐点溯源。",
                "official": "有公安部系列或台湾户政司的省级结论，"
                            "可标注「人口最多省份 / 某省第一大姓 / 台湾前十大姓」。",
                "generic": "仅见于《百家姓》或现代排名名录，无逐姓地理史料。"
                           "演示使用共用迁徙事件与近现代常见姓分布的通用骨架，"
                           "不标专属发祥地、不伪造家谱出处。",
            },
            "noPopulationWeighting": "点数不是人口数；排名只用于检索排序与近现代铺开等级，"
                                     "不摊成人口密度。",
            "pinyinFallback": fallback,
        },
        "surnames": list(rows.values()),
    }
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    lv = {}
    for r in rows.values():
        lv[r["lv"]] = lv.get(r["lv"], 0) + 1
    print("合并后共 %d 姓：%s" % (len(rows), lv))
    print("  有官方省级结论 %d 姓 / 有拼音 %d 姓（兜底 %d）"
          % (sum(1 for r in rows.values() if r["ev"]),
             sum(1 for r in rows.values() if r["py"]), fallback))
    print("  百家姓序位 %d / 现代排名 %d / 两者兼有 %d"
          % (sum(1 for r in rows.values() if r["bjx"]),
             sum(1 for r in rows.values() if r["rank"]),
             sum(1 for r in rows.values() if r["bjx"] and r["rank"])))
    print("已写出 %s（%.1f KB）" % (OUT.name, OUT.stat().st_size / 1024))
    print("样例：", json.dumps(list(rows.values())[:3], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
