# HANDOFF：姓氏源流图谱 H5 —— D 档复姓补全（57 个）

> 交接对象：接手本项目的 AI（HY3）或人工
> 最后更新：2026-11-13 23:30
> 一句话任务：给「姓氏源流图谱」H5 补上 **57 个 D 档（未入现代常见 600 名）复姓**的谱牒史料，每姓一条记录，写进 `genealogy_batch6.json`，然后重建页面。

---

## 0. 三十秒速览

| 项 | 值 |
|---|---|
| 工作目录 | `D:\WorkBuddy\2026-11-08-14-21-37\surname-atlas` |
| 线上地址 | https://surname-atlas.app.workbuddy.host/?sharecode=YNRVFHTVQT |
| 已上线版本 md5 | `8c691a6a465770faf877084693216117`（27,028,342 字节） |
| 待办 | 57 个复姓，见 `_d2_compound_progress.md` |
| 数据落点 | `genealogy_batch6.json`（已注册，直接追加） |
| 进度清单 | `_d2_compound_progress.md`（`[ ]` → `[x]`） |
| 完成度 | D 档 15 个**单姓**已完成（`genealogy_batch5.json`）；57 个**复姓**待做 |

---

## 1. 项目是什么

一个单文件 H5（约 27 MB，全部内联，可直接放公众号/微信打开）：选一个姓氏，看它在 34 个时间格里的人口迁徙动画，配「史 / 官 / 家 / 谱」四类依据角标、地图底图、背景音乐。

构建链是**两段**，别搞混：

```
genealogy_batch*.json  ──build_h5_data.py──▶  h5data/core.js（全量数据）
h5.template.html + core.js ──build.py --h5──▶  index.html（单文件成品）
```

改数据只要动 `genealogy_batch6.json`；改界面动 `h5.template.html`，改完两条命令都要跑。

---

## 2. 关键文件

| 文件 | 作用 | 能不能动 |
|---|---|---|
| `genealogy_batch6.json` | **本轮要写的文件**，57 个复姓的记录 | ✅ 只追加 |
| `_d2_compound_progress.md` | 57 个复姓的进度表 | ✅ 勾选 + 填郡望 |
| `build_h5_data.py` | 数据构建，第 251 行的批次循环已含 `genealogy_batch6.json` | ⚠️ 除加批次外不要改 |
| `h5.template.html` | 页面模板（约 1000 行） | ⚠️ 非必要不动 |
| `build.py` | `python build.py --h5` 生成 index.html | ❌ 不动 |
| `surname_list.json` | 672 个姓氏总表（含 rank/lv/cmp 字段） | ❌ **绝不动排名** |
| `_smoke_xiao.js` | 冒烟测试（9 项） | ❌ 只跑不改 |
| `_smoke_map.js` | 底图环境测试（本机 127.0.0.1） | ❌ 只跑不改 |
| `cloudfbase-input/` | 发布目录（index.html + bgm/ + _tmp/） | ✅ 只同步产物 |
| `_rollback_20261113/` | 历史回退备份 | ❌ 别删 |

---

## 3. 数据结构（照抄这个 schema）

`genealogy_batch6.json` 顶层：

```json
{
  "meta": { "version": "D-2", "generatedOn": "2026-11-13", "scope": "...", "note": "..." },
  "surnames": [ /* 一条一个姓，按顺序追加 */ ]
}
```

单条记录（这是 `genealogy_batch5.json` 里真实存在的「秋」姓，可直接当模板）：

```json
{
  "c": "秋",
  "py": "qiu",
  "basis": "少昊之后；或鲁大夫湫胡之后，以祖字去水为氏",
  "origin": {
    "dynasty": "春秋",
    "text": "秋氏源出有二：一说出自少昊（金天氏）之后，《路史》云『少昊之后有秋氏』；一说春秋鲁大夫仲孙湫之裔孙胡（湫胡）仕于陈，支庶以祖字去水为『秋』氏。另西周设秋官（司寇），后世亦有以官为氏者。",
    "wang": ["天水郡"],
    "modern": ["今甘肃天水"]
  },
  "migration": "秋氏以天水为郡望，后散居河北、山东、山西及江南，人数不多。",
  "sources": [
    { "title": "路史", "author": "宋·罗泌", "type": "家", "quote": "少昊之后有秋氏。" },
    { "title": "姓谱", "author": "", "type": "家", "quote": "春秋鲁人秋胡之后。" }
  ],
  "note": ""
}
```

字段要求：

- `c` —— 姓氏正字。复姓照写（`万俟` 不是 `万侯`，`澹台` 不是 `澹臺`，`亓官` 不是 `丌官`）
- `py` —— 拼音**连写、不带声调**：`xiahou` / `wuzhu` / `dantai` / `qiguan`
- `basis` —— 一句话得姓根据（列表页会显示）
- `origin.dynasty` —— 得姓朝代，如 `西周` / `春秋` / `战国` / `北魏` / `唐`
- `origin.text` —— 150~250 字叙述，讲清"谁、因为什么、以什么为氏"
- `origin.wang` —— **字符串数组**，郡望，如 `["谯郡"]`，多个就多个元素
- `origin.modern` —— **字符串数组**，今地，如 `["今安徽亳州"]`
- `migration` —— 一句话迁徙脉络
- `sources` —— 出处数组，`type` **固定写 `"家"`**（对应"家"角标）
- `note` —— 备注，没有就空字符串

---

## 4. 两条铁律（违反过，出过事）

### 铁律一：`wang` 和 `modern` 必须是数组

以前有人把这两个字段写成裸字符串（`"wang": "谯郡"`），结果选到那个姓时前端 `wang.join()` 直接崩、页面白掉。

写完**务必自查**：

```bash
python -c "
import json
g=json.load(open('genealogy_batch6.json',encoding='utf-8'))
bad=[r['c'] for r in g['surnames'] if not isinstance(r.get('origin',{}).get('wang'),list) or not isinstance(r.get('origin',{}).get('modern'),list)]
print('非数组字段:', bad or '无')
print('记录数:', len(g['surnames']))
"
```

### 铁律二：查不到引文就留空，绝不编

`quote` 字段只能填**真实存在的古籍原文**。查不到就把 `quote` 写成 `""`，不要自己造句、不要虚构人名年份、不要"合理推测"后写成引文。

这个项目的历史数据引过：《元和姓纂》《通志·氏族略》《姓氏考略》《姓苑》《魏书·官氏志》《路史》《潜夫论》《风俗通义》《万姓统谱》。引之前确认这本书**确实**有这句话。

宁可一条 `sources` 只有书名没有原文，也不能有一句假引文。

---

## 5. 标准作业流程

在 `D:\WorkBuddy\2026-11-08-14-21-37\surname-atlas` 下执行：

### ① 看进度，取本轮要做的姓

打开 `_d2_compound_progress.md`，按表格顺序取仍标 `[ ]` 的前 10 个（不足 10 个就全做）。表格长这样：

```
| # | 复姓 | 完成 | 郡望 |
|---|------|------|------|
| 1 | 万俟 | [ ] |  |
| 2 | 夏侯 | [ ] |  |
```

顺序是：万俟、夏侯、诸葛、闻人、东方、赫连、皇甫、尉迟、公羊、澹台、公冶、宗政、濮阳、淳于、单于、太叔、申屠、公孙、仲孙、轩辕、钟离、宇文、长孙、慕容、鲜于、闾丘、司徒、司空、亓官、司寇、仉督、子车、颛孙、端木、巫马、公西、漆雕、乐正、壤驷、公良、拓跋、夹谷、宰父、谷梁、段干、百里、东郭、南门、呼延、羊舌、微生、梁丘、左丘、东门、西门、南宫、第五。

### ② 逐姓核实

每个姓都要查清：得姓来源（何人 / 何国 / 何邑 / 改姓）、朝代、郡望、今地、代表名人、可引古籍原文。

复姓多半有两个以上源头（比如 慕容 = 鲜卑慕容部 + 高辛氏后裔传说；拓跋 = 鲜卑拓跋部，北魏孝文改元氏而留支庶），**多源头就写多源头**，不要强行归一。

### ③ 追加进 `genealogy_batch6.json`

只往 `surnames` 数组里 append，**不要覆盖已有记录**（可能上一轮已经写过几条）。

### ④ 重建数据

```bash
python build_h5_data.py
```

必须看到最后一行含 **「校验 通过」**。正常输出长这样：

```
核心数据 26339.5 KB / 点位库 3137 条 / 时间轴 34 格 / 事件 19 条 / 姓氏 672 个
逐姓 full 帧：551 个文件，合计 25368.5 KB
自检：通用事件格 24 / 含专属事件格 4 / 专属事件 4 条 / 校验 通过
```

### ⑤ 重建页面

```bash
python build.py --h5
```

输出 `已生成：...\index.html（公众号 H5，26394.9 KB，单文件自包含）`。

### ⑥ 冒烟测试

```bash
node _smoke_xiao.js
```

要求 **PASS 9 / FAIL 0**。

> 允许出现的唯一"错误"是：`腾讯地图 JavaScript API 不支持在file协议使用`。这是 `file://` 协议下腾讯地图 SDK 的固有限制，**不是 bug**，线上 https 正常。

### ⑦ 同步发布包 + zip

```bash
cp index.html cloudfbase-input/index.html
cd cloudfbase-input && python - <<'PY'
import zipfile, os, hashlib
src='cloudfbase-input.zip'
z=zipfile.ZipFile(src,'w',zipfile.ZIP_DEFLATED)
for root,_,files in os.walk('.'):
    for f in files:
        if f==src or f.endswith('.bak'): continue
        p=os.path.join(root,f)
        z.write(p,'cloudfbase-input/'+os.path.relpath(p,'.'))
z.close()
o=hashlib.md5(open('index.html','rb').read()).hexdigest()
n=hashlib.md5(zipfile.ZipFile(src).read('cloudfbase-input/index.html')).hexdigest()
print('外部:',o,' zip内:',n,' 一致:',o==n)
PY
```

必须看到 `一致: True`。**zip 里一定要有 `bgm/Victory.mp3`**，漏了线上就没背景音乐。

### ⑧ 更新进度表

本轮完成的姓：`[ ]` 改 `[x]`，并在「郡望」列填上郡望。

---

## 6. 禁止事项

1. **不要发布上线。** 发布 = 覆盖正在分享的线上链接，必须由用户当轮明确说"发布/上线"才行。定时任务只负责数据、构建、zip。
2. **不要改 `surname_list.json` 里的 `rank` / `lv`。** 排名是真实公开数据（肖排 33、萧排 101 就是这么来的），不是我们编的，改了就是造假。
3. **不要动 `h5.template.html` 里这几处已定稿的改动**（见下一节），它们都是踩坑后修好的。
4. **不要把 `_tmp/` 从 `cloudfbase-input/` 里删掉**，发布流程会用到。
5. **不要用 `rm -rf` 清目录**，备份目录 `_rollback_20261113/` 要留着。

---

## 7. 已定稿、别改回去的地方

这些是前几轮反复修好的，改动前先看懂再动：

| 位置 | 现状 | 为什么 |
|---|---|---|
| 标题 | `ch+'姓的历史轨迹'` | 用户明确要求去掉"34格看完" |
| 播放时钟 | `setInterval` + `stepClock`（每 33ms 推进墙钟） | 早期版本用 requestAnimationFrame，后台标签页会卡住 |
| 节奏 | `BASE_MS=550` / `EVENT_MS=380`，**有迁徙事件的格再 ×1.1** | 用户要求把事件世纪延长 10%，总时长 34.2 秒 |
| 背景音乐 | `bgm/Victory.mp3`，音量 0.4，**结尾 2.6 秒线性淡出** | 用户反馈硬切太突兀 |
| 肖 / 萧 | 互为"另一条"的对称说明，标题「同源，已分列」 | 见下 |
| 地图 Key | 见 `_KEY.md`（不入库，本地构建/部署时填回；或网址 `?tk=你的Key` 自助注入） | 公开仓库不含密钥 |
| 地图降级 | `proxyUsable()` 校验占位符 | 修预览面板"底图初始化失败：undefined" |

### 关于肖 / 萧（重要，别改回去）

- 事实：**同源，已分列**。萧是正字本姓（兰陵萧氏、萧何、南朝齐梁）；1977 年《第二次汉字简化方案（草案）》把「萧」简化为「肖」，1986 年废止，但**大量萧姓已按「肖」登记在户籍证件上**并沿用至今。
- 所以肖排 33、萧排 101 是**真实排名**，不是错误——肖的人口多，很大程度正是那段改登记的沉淀。
- 页面里两者都保留**各自真实排名和档位**，用对称的互链说明讲清关系。
- **不要**把两者合并、**不要**把它们改成同一档位、**不要**写"肖不是独立姓氏"（这句话和"肖排前 100"直接矛盾，用户已经指出过）。

### 关于地图那行报错（别当 bug 修）

`底图未加载：…（已降级为行政基底点模式）` 只在 **localhost / 127.0.0.1** 显示，因为 `diag()` 自带 hostname 判断，公网用户看不到。

`proxyHost` 里的 `__WB_HTTP_PORT__` 占位符在静态构建里**不会被替换**，所以 `proxyUsable()` 会主动跳过代理、改走自有 Key。这是有意为之，别把校验删掉。

---

## 8. 排查手册

| 症状 | 原因 | 处理 |
|---|---|---|
| 选某个姓页面白掉 | 该姓 `wang` / `modern` 不是数组 | 跑第 4 节的数组自查，改成数组重建 |
| `build_h5_data.py` 报错 | JSON 语法错（多逗号、缺引号） | `python -c "import json;json.load(open('genealogy_batch6.json',encoding='utf-8'))"` 定位 |
| 新姓没有"家"角标 | 记录没进 batch6，或 `type` 不是 `"家"` | 检查记录 `sources[].type` 与文件是否被批次循环读到 |
| 线上没有背景音乐 | zip 里漏了 `bgm/` | 按第 5 节⑦重建，确认列出 `bgm/Victory.mp3` |
| 微信里还是旧版 | webview 缓存 | 分享链接后加 `&v=时间戳` 强制重拉 |
| 底图空白 | Key 域名白名单 / 未配安全密钥 | 公网正常则不用管；本机预览空白属正常 |

---

## 9. 本轮完成后的验收

- [x] 57 个复姓在 `_d2_compound_progress.md` 里全部为 `[x]`，郡望列已填
- [x] `genealogy_batch6.json` 有 57 条记录，无字段类型错误
- [x] `build_h5_data.py` 输出「校验 通过」
- [x] `node _smoke_xiao.js` 为 PASS 9 / FAIL 0
- [x] zip 内 index.html 的 md5 与外部一致，且含 `bgm/Victory.mp3`
- [x] 没有自动发布（等用户发话）

---

## 10. 环境备注

- Python 命令是 `python`（不是 `python3`）
- Node 已装，Playwright chromium 在
  `C:\Users\Administrator\AppData\Local\ms-playwright\chromium-1187\chrome-win\chrome.exe`
- 本机底图测试：`node _smoke_map.js`（自带 `127.0.0.1:18731` 静态服务）
- `index.html` 约 27 MB，每次重建 + zip 约 30 秒，属正常
