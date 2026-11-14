<img width="660" height="416" alt="下载" src="https://github.com/user-attachments/assets/83cd0ea5-dfb9-442a-8fd4-85934f9270a5" />

# 姓氏繁衍 H5（TigerFRM）

选一个姓，看它从得姓、扩散、迁徙到繁衍的两千年。34 格共用百年时间轴，19 次大型迁徙事件，纯点密度可视化。

## 版本
- **v2.0.0**（2026-11-14 发布）
  - 各姓「来历（得姓来源）+ 迁徙简介」改为**常驻展示**：手机竖屏顶部小卡、电脑横屏右侧栏，不遮挡地图。
- **v1.0.5**（2026-11-14 发布）
  - 共 672 个姓氏（单姓 + 复姓）。其中 57 个 D 档复姓（万俟、夏侯、诸葛、东方、赫连、皇甫、尉迟、公羊、澹台、公冶、宗政、濮阳、淳于、单于、太叔、申屠、公孙、仲孙、轩辕、钟离、宇文、长孙、慕容、鲜于、闾丘、司徒、司空、亓官、司寇、仉督、子车、颛孙、端木、巫马、公西、漆雕、乐正、壤驷、公良、拓跋、夹谷、宰父、谷梁、段干、百里、东郭、南门、呼延、羊舌、微生、梁丘、左丘、东门、西门、南宫、第五）带「家·谱牒依据」角标、郡望、出处文献。

## 仓库说明（构建产物不入仓）
本仓库是**源码与数据**，以下由脚本生成的较大产物**不纳入版本控制**（见 `.gitignore`），克隆后按需重建：
- `century_atlas.json` ← `python build_century_atlas.py`
- `genealogy.json` ← `python compile_genealogy.py`
- `h5data/`、`index.html`、`cinema.html` ← `python build_h5_data.py` + `python build.py --h5`
- `video_out/`（出片视频）、`*.zip`（发包备份）、`bgm/`、`node_modules/`、`.workbuddy/`（含分享码，勿公开）

完整构建流程：见「本地预览」一节。

## 目录结构
- `h5.template.html` —— 主页面模板（地图 + 时间轴 + 详情卡）。构建时把全量数据内联进去生成 `index.html`。
- `build_h5_data.py` —— 读取各 `genealogy_batch*.json` 与数据 json，产出 `h5data/core.js`（全量数据）。
- `build.py --h5` —— 把 `h5data/core.js` 内联进 `h5.template.html` → `index.html`。
- `genealogy_batch1..6.json` —— 逐姓史料（得姓来源、郡望、迁徙、出处文献）。
- `cinema.template.html` / `cinema.html` —— 影院版（可选）。

## 本地预览
1. `python build_h5_data.py`（输出「校验 通过」）
2. `python build.py --h5`（生成 `index.html`）
3. 用浏览器或静态服务器打开 `index.html`（地图在本机走密钥代理，公网需自备腾讯地图 Key）。

## 部署
`cloudfbase-input/`（含 `index.html` + `bgm/Victory.mp3`）经 WorkBuddy「发布为应用」上线，域名 `surname-atlas.app.workbuddy.host`。

## 数据合规
底图使用腾讯地图 JS API GL 默认矢量底图（官方、带审图号）；仅在其上叠加离散点，**不绘制、不修改任何国界 / 省界 / 历史疆域，不做分省设色**。
