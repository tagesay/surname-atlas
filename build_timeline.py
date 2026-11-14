# -*- coding: utf-8 -*-
"""
生成共用时间轴 timeline.json 与迁徙事件年表 migration_events.json。

标准（用户 2026-11-13 确认）
--------------------------
· 所有姓共用一条时间轴，起点留给最早得姓的姓。
· 西周分封以前拉长步长，只做起源示意（3 格：夏及先夏 / 商 / 西周分封）。
· 分封之后从前 10 世纪起，严格每 100 年一格，到 21 世纪（截 2026），共 31 格。
· 合计 34 格。

颗粒度：三层混合
  · 史料锚点（发祥地/郡望/迁入地）落县级（2718 区县 + 22 台湾县市）
  · 迁徙走廊节点、省内铺开用地级市（363）
  · 官方宏观结论（31 省均有分布）落省级（34）
  · 家谱里的乡名归并到所属县，原始乡名保留在 basis 里，不单独标点

依据：事件级
  · 一条迁徙事件的出处覆盖它带出的一组县，每点仍标事件名与出处编号
  · A 正史/官方统计 · B 地方志/族谱 · C 学界通行说法
  · 早期粗步长格明确标为「传说/后世追述」，不与同期史料混同
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# ---------- 朝代标注（只做时间轴刻度，不是口播文案） ----------
def dynasty_of(century):
    """century: 负=公元前。返回该世纪主要政权（用于刻度标注）。"""
    if century is None:
        return ""
    c = century
    if c == -21: return "夏（传说）"
    if c == -16: return "商"
    if c == -11: return "西周"
    if c <= -8:  return "西周"
    if c <= -6:  return "春秋"
    if c <= -3:  return "战国"
    if c == -2:  return "秦 · 西汉"
    if c == -1:  return "西汉"
    if c == 1:   return "东汉"
    if c == 2:   return "东汉 · 三国"
    if c == 3:   return "三国 · 西晋"
    if c == 4:   return "东晋 · 十六国"
    if c == 5:   return "南北朝"
    if c == 6:   return "南北朝 · 隋"
    if c == 7:   return "唐"
    if c == 8:   return "唐"
    if c == 9:   return "晚唐 · 五代"
    if c == 10:  return "五代 · 北宋"
    if c == 11:  return "北宋"
    if c == 12:  return "宋（南渡）"
    if c == 13:  return "南宋 · 元"
    if c == 14:  return "元末 · 明初"
    if c == 15:  return "明"
    if c == 16:  return "明"
    if c == 17:  return "明末 · 清初"
    if c == 18:  return "清"
    if c == 19:  return "清 · 晚清"
    if c == 20:  return "近现代"
    if c == 21:  return "当代"
    return ""


def century_label(century):
    if century is None:
        return "起源示意"
    return ("前%d世纪" % abs(century)) if century < 0 else ("%d世纪" % century)


def century_range(century):
    """世纪 → 公元年区间（负为公元前）。"""
    if century is None:
        return [-2070, -1047]
    if century < 0:
        a = abs(century)
        return [-(a * 100), -((a - 1) * 100 + 1)]
    return [(century - 1) * 100 + 1, century * 100]


# ---------- 34 格时间轴 ----------
def build_timeline():
    steps = []
    # 早期 3 格：拉长步长，只做起源示意，明确标注非同期史料
    early = [
        ("e0", [-21, -17], "夏及先夏", "姓族起源（传说）",
         "约前2070–前1600。此期无同期姓氏地理分布记录；画面只标后世追述的得姓传说地。"),
        ("e1", [-16, -11], "商", "族氏初分（传说）",
         "约前1600–前1046。姓、氏分立，传世文献仍无「某姓在某地」的同期记录。"),
        ("e2", [-11, -11], "西周", "分封 · 以国为氏",
         "前1046 起。周代分封，以国、以邑为氏，多数大姓自此有可考发源地。"),
    ]
    for sid, cs, dyn, label, note in early:
        c0, c1 = cs
        steps.append({
            "id": sid,
            "label": label,
            "era": ("%s—%s · %s" % (century_label(c0), century_label(c1), dyn))
                    if c0 != c1 else ("%s · %s" % (century_label(c0), dyn)),
            "centuryStart": c0,
            "centuryEnd": c1,
            "yearStart": century_range(c0)[0],
            "yearEnd": century_range(c1)[1],
            "dynasty": dyn,
            "mode": "origin",          # 起源示意，不是同期史料
            "evidenceTier": "传说/后世追述",
            "note": note,
            "spanYears": None,
        })
    # 前 10 世纪 → 21 世纪，每 100 年一格
    for c in list(range(-10, 0)) + list(range(1, 22)):
        yr = century_range(c)
        steps.append({
            "id": "c%s" % (("m%02d" % abs(c)) if c < 0 else ("a%02d" % c)),
            "label": century_label(c),
            "era": "%s · %s" % (century_label(c), dynasty_of(c)),
            "centuryStart": c,
            "centuryEnd": c,
            "yearStart": yr[0],
            "yearEnd": min(yr[1], 2026) if c == 21 else yr[1],
            "dynasty": dynasty_of(c),
            "mode": "century",
            "evidenceTier": None,
            "note": "",
            "spanYears": 100 if c != 21 else yr[1] - yr[0] + 1,
        })
    return {
        "meta": {
            "version": "2.0.0",
            "title": "共用百年时间轴 · 34 格",
            "shared": "所有姓共用同一条时间轴；起点留给最早得姓的姓，其他姓在各自首现格之后才出现。",
            "earlyMode": "西周分封以前拉长步长，只做起源示意；不冒充同期史料。",
            "stepMode": "分封之后（前10世纪起）严格每100年一格。",
            "count": len(steps),
            "coordinateStandard": "GCJ-02；台湾省及海外按官方 FAQ 使用 WGS84。",
            "compliance": "不画任何国界/省界/历史疆域轮廓，不做分省设色；只用离散点密度。",
        },
        "steps": steps,
    }


# ---------- 迁徙事件年表 ----------
# tier: A 正史/官方统计 · B 地方志/族谱 · C 学界通行说法
# scope: "all" 表示所有姓都受该事件影响；否则列出涉及姓
# from/to: 地名（运行时解析到 places.json 的 adcode，优先县级、退地级市）
EVENTS = [
    {
        "id": "ev_zhou_feng", "name": "西周分封 · 以国为氏",
        "start": -11, "end": -10, "tier": "A",
        "source": "《史记·周本纪》《左传》；武王克商后分封诸侯，以国为氏、以邑为氏。",
        "from": ["陕西省/西安市"], "to": [
            "河南省/周口市/淮阳区", "河南省/信阳市/潢川县", "山西省/临汾市/洪洞县",
            "江苏省/苏州市", "河南省/许昌市", "甘肃省/天水市", "山西省/太原市"],
        "scope": "all",
        "note": "多数大姓的可考发源地自此形成。",
    },
    {
        "id": "ev_chunqiu", "name": "春秋战国 · 诸侯兼并、以邑为氏",
        "start": -8, "end": -3, "tier": "A",
        "source": "《左传》《史记·世家》；国灭后子孙以国为氏，士大夫以邑为氏。",
        "from": ["河南省/洛阳市"], "to": [
            "山东省/临沂市", "河北省/邢台市/清河县", "江苏省/徐州市",
            "河北省/保定市/定州市", "河南省/驻马店市/汝南县"],
        "scope": "all", "note": "郡望雏形出现。",
    },
    {
        "id": "ev_qin_han", "name": "秦汉 · 迁豪强、分封同姓",
        "start": -3, "end": -1, "tier": "A",
        "source": "《史记·秦始皇本纪》《汉书·高帝纪》；秦徙六国豪强于关中，汉分封同姓王。",
        "from": ["陕西省/咸阳市"], "to": [
            "陕西省/西安市", "江苏省/徐州市", "河南省/开封市",
            "河北省/保定市/定州市", "甘肃省/天水市"],
        "scope": "all", "note": "",
    },
    {
        "id": "ev_yongjia", "name": "永嘉之乱 · 衣冠南渡",
        "start": 4, "end": 6, "tier": "A",
        "source": "《晋书·王导传》《宋书·州郡志》；311 年洛阳陷落，中原士族大批渡江，东晋于江南侨置郡县。",
        "from": ["河南省/洛阳市", "山东省/临沂市", "山西省/太原市"], "to": [
            "江苏省/南京市", "浙江省/绍兴市", "江苏省/镇江市",
            "湖北省/武汉市/江夏区", "江苏省/常州市"],
        "scope": "all", "note": "第一次大规模南迁，江南姓氏格局奠基。",
    },
    {
        "id": "ev_kaizhang", "name": "唐初开漳 · 陈政陈元光入闽",
        "start": 7, "end": 7, "tier": "B",
        "source": "《漳州府志》《陈氏族谱》；唐总章二年（669）陈政、陈元光率固始籍军民入闽平乱、置漳州。",
        "from": ["河南省/信阳市/固始县"], "to": [
            "福建省/漳州市", "福建省/泉州市"],
        "scope": ["陈"], "note": "闽南陈姓主源。",
    },
    {
        "id": "ev_anshi", "name": "安史之乱 · 南迁深入江南、江西",
        "start": 8, "end": 9, "tier": "A",
        "source": "《旧唐书·地理志》《资治通鉴》；755—763 年战乱，人口大量南移，江西成为入闽中转。",
        "from": ["陕西省/西安市", "河南省/洛阳市"], "to": [
            "江西省/南昌市", "浙江省/杭州市", "江西省/吉安市/泰和县",
            "福建省/南平市/邵武市", "湖南省/长沙市"],
        "scope": "all", "note": "",
    },
    {
        "id": "ev_kaimin", "name": "唐末 · 王潮王审知入闽",
        "start": 9, "end": 10, "tier": "B",
        "source": "《新唐书·王潮传》《十国春秋》；885 年王潮、王审知自光州固始率军入闽，后建立闽国。",
        "from": ["河南省/信阳市/固始县"], "to": [
            "福建省/泉州市", "福建省/福州市", "福建省/漳州市"],
        "scope": ["王"], "note": "「开闽王氏」；同批入闽军民亦含多姓。",
    },
    {
        "id": "ev_huangqiao", "name": "后周 · 黄峭山遣子外迁",
        "start": 10, "end": 10, "tier": "B",
        "source": "《黄氏族谱》邵武黄峭山遣子诗；后周广顺元年（951）遣十八子分迁闽粤赣。",
        "from": ["福建省/南平市/邵武市"], "to": [
            "福建省/泉州市", "广东省/梅州市", "江西省/南昌市",
            "广东省/汕头市"],
        "scope": ["黄"], "note": "",
    },
    {
        "id": "ev_yimen", "name": "北宋 · 义门陈氏奉旨分庄",
        "start": 11, "end": 11, "tier": "B",
        "source": "《宋史·陈兢传》《义门陈氏宗谱》；嘉祐七年（1062）奉旨分庄，一次散至全国多地。",
        "from": ["江西省/九江市/德安县"], "to": [
            "江西省/南昌市", "湖北省/武汉市", "湖南省/长沙市",
            "四川省/成都市", "浙江省/杭州市", "广东省/广州市"],
        "scope": ["陈"], "note": "有组织的一次性全国性扩散。",
    },
    {
        "id": "ev_jingkang", "name": "靖康之难 · 宋室南渡",
        "start": 12, "end": 13, "tier": "A",
        "source": "《宋史·高宗本纪》《建炎以来系年要录》；1127 年宋室南渡，宗族经海路入泉州、陆路经赣湘入闽粤。",
        "from": ["河南省/开封市"], "to": [
            "浙江省/杭州市", "福建省/泉州市", "福建省/福州市",
            "江西省/吉安市/泰和县", "广东省/广州市"],
        "scope": "all", "note": "第三次南迁高潮，南方人口优势确立。",
    },
    {
        "id": "ev_hongdong", "name": "明初 · 洪洞大槐树移民",
        "start": 14, "end": 15, "tier": "B",
        "source": "《明史·食货志》《洪洞县志》；洪武、永乐年间自山西洪洞集散，迁往华北、中原数省。",
        "from": ["山西省/临汾市/洪洞县"], "to": [
            "河北省/石家庄市", "山东省/济南市", "河南省/郑州市",
            "北京市", "陕西省/西安市", "甘肃省/兰州市"],
        "scope": "all", "note": "华北姓氏格局重塑。",
    },
    {
        "id": "ev_mingchuan", "name": "元末明初 · 明玉珍部入川（第一次湖广填四川）",
        "start": 14, "end": 14, "tier": "B",
        "source": "《明氏实录》《大竹县志》；元至正十八年（1358）明玉珍统兵入川，部众多落籍重庆至成都沿途各县；洪武四年后复迁楚之麻、黄人实蜀。",
        "from": ["湖北省/黄冈市/麻城市", "湖北省/随州市"], "to": [
            "重庆市", "四川省/成都市", "四川省/达州市", "四川省/广安市"],
        "scope": "all", "note": "麻城孝感乡为共同祖源地记忆，乡名归并到麻城市保留于依据。",
    },
    {
        "id": "ev_jiangxi_huguang", "name": "明清 · 江西填湖广",
        "start": 15, "end": 17, "tier": "B",
        "source": "清魏源《湖广水利论》「江西填湖广，湖广填四川」；吉安泰和、鹅公大丘等为族谱常见祖源地。",
        "from": ["江西省/吉安市/泰和县", "江西省/南昌市"], "to": [
            "湖南省/长沙市", "湖北省/武汉市", "湖北省/黄冈市/麻城市"],
        "scope": "all", "note": "",
    },
    {
        "id": "ev_tianchuan", "name": "清初 · 《招民填川诏》湖广填四川高峰",
        "start": 17, "end": 18, "tier": "A",
        "source": "《清圣祖实录》《四川通志》；康熙《招民填川诏》后百余年约 600 万人入川，四川人口 1757 年 268 万 → 1790 年 888 万 → 1830 年 3495 万。清末《成都通览》记成都人原籍湖广占 25%。",
        "from": ["湖北省/黄冈市/麻城市", "湖南省/长沙市", "江西省/南昌市",
                 "广东省/梅州市", "福建省/龙岩市"], "to": [
            "四川省/成都市", "重庆市", "四川省/内江市", "四川省/自贡市",
            "四川省/德阳市", "四川省/资阳市", "四川省/广安市",
            "四川省/达州市", "四川省/南充市"],
        "scope": "all",
        "note": "第二次填川，历时百余年；水路沿长江经三峡、陆路经川黔川鄂小道。",
    },
    {
        "id": "ev_dutai", "name": "明末清初 · 渡海赴台",
        "start": 17, "end": 19, "tier": "B",
        "source": "《台湾府志》《台湾通史》；1661 年郑成功渡台，1683 年后闽粤移民大批入台，陈姓为台湾省第一大姓。",
        "from": ["福建省/泉州市", "福建省/漳州市", "广东省/梅州市",
                 "广东省/汕头市"], "to": [
            "台湾省/台南市", "台湾省/高雄市", "台湾省/新北市",
            "台湾省/彰化县", "台湾省/嘉义县"],
        "scope": "all", "note": "",
    },
    {
        "id": "ev_zouxikou", "name": "清—民国 · 走西口",
        "start": 18, "end": 19, "tier": "B",
        "source": "《山西通志》《绥远通志稿》；晋陕北部居民经杀虎口等关口迁往内蒙古中西部垦殖、经商。",
        "from": ["山西省/忻州市", "山西省/朔州市", "陕西省/榆林市"], "to": [
            "内蒙古自治区/呼和浩特市", "内蒙古自治区/包头市",
            "内蒙古自治区/鄂尔多斯市", "内蒙古自治区/巴彦淖尔市"],
        "scope": "all", "note": "",
    },
    {
        "id": "ev_chuangguandong", "name": "晚清—民国 · 闯关东",
        "start": 19, "end": 20, "tier": "A",
        "source": "《清史稿·食货志》《东北移民史》；1860 年东北部分开禁后鲁冀豫民大批迁入，20 世纪初形成高峰。",
        "from": ["山东省/烟台市", "山东省/潍坊市", "河北省/唐山市",
                 "河南省/安阳市"], "to": [
            "辽宁省/沈阳市", "辽宁省/大连市", "吉林省/长春市",
            "黑龙江省/哈尔滨市", "黑龙江省/齐齐哈尔市"],
        "scope": "all", "note": "东北姓氏格局由此形成。",
    },
    {
        "id": "ev_xiananyang", "name": "近代 · 下南洋",
        "start": 19, "end": 20, "tier": "C",
        "source": "《华侨华人史》等学界通行研究；闽粤沿海居民出洋谋生。海外不在本图地理范围内，仅作文字说明，不落点。",
        "from": ["福建省/泉州市", "广东省/汕头市"], "to": [],
        "scope": "all", "note": "不落点：地理范围限中国境内。",
    },
    {
        "id": "ev_xiandai", "name": "近现代 · 常见姓氏 31 省均有分布",
        "start": 20, "end": 21, "tier": "A",
        "source": "公安部户政管理研究中心《二〇二一年全国姓名报告》：常见姓氏在全国 31 个省（区、市）均有分布；《二〇一九年全国姓名报告》各省第一大姓表；《二〇二一年全国姓名报告》各姓人口最多省份表。",
        "from": [], "to": [],
        "scope": "all",
        "note": "触发省内铺开模型：省级结论 → 地级市铺开；港澳台依各自户政统计单列。",
    },
]


# ---------- 事件背景简介（画面右下角标注用，不是口播文案） ----------
# 每条 1~2 句，只写「为什么会发生这次迁徙」，全部取自本条事件 source/note 里
# 已核实的史实，不新增未经核查的细节。用户 2026-11-13 要求标注时同时简介背景。
EVENT_BRIEFS = {
    "ev_zhou_feng":
        "前 1046 年武王克商后分封诸侯，以国为氏、以邑为氏。多数大姓可考的发源地与郡望，都从这一轮分封开始形成。",
    "ev_chunqiu":
        "春秋战国诸侯兼并，国灭之后子孙以国为氏，士大夫以采邑为氏。姓氏从少数贵族扩散到士人阶层，郡望雏形出现。",
    "ev_qin_han":
        "秦统一后徙六国豪强于关中，汉又分封同姓王、迁豪族实陵邑。政治性强制迁移把东方大姓带进关中和各地封国。",
    "ev_yongjia":
        "311 年永嘉之乱洛阳陷落，中原士族大批渡江，东晋在江南侨置郡县安置流民。第一次大规模南迁，江南姓氏格局由此奠基。",
    "ev_kaizhang":
        "唐总章二年（669）陈政、陈元光率固始籍军民入闽平乱并奏置漳州。这批军民落籍闽南，成为闽南陈姓主源，也是「开漳圣王」信仰的由来。",
    "ev_anshi":
        "755—763 年安史之乱，北方人口大量南移，江西成为继续入闽的中转站。南迁不再止于江淮，开始深入江南与赣闽。",
    "ev_kaimin":
        "885 年王潮、王审知自光州固始率军入闽，后建立闽国。随行军民含多姓，其中王氏被称为「开闽王氏」。",
    "ev_huangqiao":
        "后周广顺元年（951），邵武黄峭山遣十八子分迁闽、粤、赣，事见《黄氏族谱》所载遣子诗。是一次有谱可稽的家族主动扩散。",
    "ev_yimen":
        "北宋嘉祐七年（1062），聚居江西德安的义门陈氏奉旨分庄，一次拆散到全国多地。罕见的有组织、一次性全国扩散。",
    "ev_jingkang":
        "1127 年靖康之难、宋室南渡，宗族一路经海路入泉州，一路经赣湘入闽粤。第三次南迁高潮后，南方人口优势确立。",
    "ev_hongdong":
        "洪武、永乐年间，官府自山西洪洞设局集散，迁民往华北、中原数省填实战后荒地。「山西洪洞大槐树」由此成为北方共同的祖源记忆。",
    "ev_mingchuan":
        "元至正十八年（1358）明玉珍统兵入川，部众多落籍重庆至成都沿途各县；洪武四年后又迁湖广麻城、黄州人实蜀。第一次湖广填四川。",
    "ev_jiangxi_huguang":
        "明清之际「江西填湖广、湖广填四川」的连锁移民，吉安泰和、鹅公大丘等地名是南方族谱里最常见的祖源地。",
    "ev_tianchuan":
        "康熙《招民填川诏》后百余年约 600 万人入川，四川人口 1757 年 268 万增至 1830 年 3495 万。清末《成都通览》记成都人原籍湖广者占 25%。",
    "ev_dutai":
        "1661 年郑成功渡台，1683 年清廷平台后闽粤移民大批入台。陈姓至今是台湾省第一大姓，台湾县市点位即由此展开。",
    "ev_zouxikou":
        "清至民国，晋北、陕北居民经杀虎口等关口出塞，到内蒙古中西部垦殖、经商。与「闯关东」并称近代两大北向移民潮。",
    "ev_chuangguandong":
        "1860 年东北部分开禁，鲁、冀、豫灾民大批迁往辽吉黑，20 世纪初形成高峰。东北的姓氏格局基本由这一波奠定。",
    "ev_xiananyang":
        "近代闽粤沿海居民出洋谋生，形成下南洋潮。因地理范围限中国境内，本片只作说明、不落点。",
    "ev_xiandai":
        "公安部《二〇二一年全国姓名报告》：常见姓氏在全国 31 个省（区、市）均有分布。此处把省级结论展开为地级市铺开点，不按人口密度加权。",
}


# ---------- 迁徙走廊：事件覆盖区域按「地级市」铺开 ----------
# 三层混合颗粒度的第二层。注意这不是「每个市都有该姓的确切记载」，
# 而是把该事件覆盖的地理范围用行政中心点表示出来；每点仍只挂事件名与同一条出处
# （事件级依据），不伪造逐点出处。
CORRIDOR_PROVINCES = {
    "ev_yongjia":          ["江苏省", "浙江省", "安徽省", "江西省"],
    "ev_anshi":            ["江西省", "浙江省", "湖南省", "福建省"],
    "ev_jingkang":         ["浙江省", "福建省", "江西省", "广东省"],
    "ev_hongdong":         ["河北省", "山东省", "河南省", "北京市", "天津市", "陕西省", "甘肃省"],
    "ev_mingchuan":        ["四川省", "重庆市"],
    "ev_jiangxi_huguang":  ["湖南省", "湖北省"],
    "ev_tianchuan":        ["四川省", "重庆市"],
    "ev_dutai":            ["台湾省"],
    "ev_zouxikou":         ["内蒙古自治区"],
    "ev_chuangguandong":   ["辽宁省", "吉林省", "黑龙江省"],
}

# 走西口的目的地是内蒙古中西部（杀虎口—归化城—河套一线），
# 东部四盟市属东北移民/其他通道，不并入该事件。
CORRIDOR_EXCLUDE_NAMES = {
    "ev_zouxikou": {"呼伦贝尔市", "兴安盟", "通辽市", "赤峰市"},
}


def corridor_points(provinces, places):
    """取指定省份下的地级市中心点；直辖市取省级点本身；台湾省取县市点。"""
    out = []
    for v in places.values():
        path = v.get("path", "")
        for prov in provinces:
            hit = (path == prov) or path.startswith(prov + "/")
            if not hit:
                continue
            lv = v["level"]
            if lv in ("city", "county") or (lv == "province" and path == prov):
                out.append(path)
            break
    return out


def build_events():
    places = json.loads((ROOT / "places.json").read_text(encoding="utf-8"))
    events = []
    for e in EVENTS:
        x = dict(e)
        provs = CORRIDOR_PROVINCES.get(e["id"], [])
        extra = []
        if provs:
            extra = [p for p in corridor_points(provs, places)
                     if p.split("/")[-1] not in CORRIDOR_EXCLUDE_NAMES.get(e["id"], set())]
        seen, to = set(), []
        for p in list(e["to"]) + extra:
            if p not in seen:
                seen.add(p)
                to.append(p)
        x["to"] = to
        x["brief"] = EVENT_BRIEFS.get(e["id"], "")
        x["corridorProvinces"] = provs
        x["corridorPoints"] = len(extra)
        if provs:
            x["corridorNote"] = (
                "另按事件覆盖区域补入 %d 个地级市/县市中心点作为迁徙走廊骨架；"
                "这些点只表示事件波及范围，不表示逐市有独立史料记载。" % len(extra))
        events.append(x)
    return {
        "meta": {
            "version": "2.0.0",
            "count": len(events),
            "tiers": {
                "A": "正史 / 官方统计 / 政府发布",
                "B": "地方志 / 族谱 / 政府史志办",
                "C": "学界通行说法（只作背景，不单独驱动点位）",
            },
            "semantics": "事件级依据：一条出处覆盖该事件带出的一组县；每个点仍标事件名与出处编号，不伪造每点独立出处。",
            "window": "事件在 start→end 世纪窗口内逐格给迁入地增加点密度，而非一次性冒出。",
            "granularity": "三层混合：史料锚点落县级；迁徙走廊与省内铺开用地级市；官方宏观结论落省级。家谱乡名归并所属县并保留在依据文本中。",
            "corridorSemantics": "走廊点位只表示事件波及的地理范围（行政中心骨架），不代表逐市有独立记载；出处仍为该事件本身的史籍/方志。",
            "briefSemantics": "brief 为画面右下角的事件背景简介（1~2 句，不是口播文案），只写「为什么会发生这次迁徙」，全部取自该条事件已核实的 source/note。",
            "genealogyUsage": "族谱/宗谱用作事件级依据：确认某族某时自某地迁往某地，落点到所属县市，乡名归并到县并保留在 basis；不把家谱世系逐代换算成人口或点密度。",
            "compliance": "地理范围限中国境内；下南洋等海外扩散只作说明，不落点。不画任何边界线、不做分省设色。",
        },
        "events": events,
    }


def main():
    tl = build_timeline()
    ev = build_events()
    (ROOT / "timeline.json").write_text(
        json.dumps(tl, ensure_ascii=False, indent=1), encoding="utf-8")
    (ROOT / "migration_events.json").write_text(
        json.dumps(ev, ensure_ascii=False, indent=1), encoding="utf-8")
    print("timeline.json：%d 格" % len(tl["steps"]))
    print("  早期粗步长：%d 格" % sum(1 for s in tl["steps"] if s["mode"] == "origin"))
    print("  百年步长：%d 格" % sum(1 for s in tl["steps"] if s["mode"] == "century"))
    print("  首格 %s / 末格 %s" % (tl["steps"][0]["era"], tl["steps"][-1]["era"]))
    print("migration_events.json：%d 条事件" % len(ev["events"]))
    for e in ev["events"]:
        print("  %-4s %-28s %s→%s  %s  迁入地 %d 处%s" %
              (e["tier"], e["name"], e["start"], e["end"],
               ("全部姓" if e["scope"] == "all" else "/".join(e["scope"])),
               len(e["to"]),
               ("（含走廊 %d）" % e["corridorPoints"] if e["corridorPoints"] else "")))


if __name__ == "__main__":
    main()
