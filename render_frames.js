/* 批量出片：把页面按「姓 × 朝代」渲染成 PNG 序列，再用 ffmpeg 合成视频。
 *
 * 为什么这样出片
 * --------------
 * 页面的点密度是自绘 canvas，底图是腾讯地图 GL。逐帧用无头浏览器截图，
 * 再交给 ffmpeg 合成，是唯一能保证「画面与页面完全一致」的路子：
 * 不重新实现一遍绘图逻辑，就不会��现页面和成片两套效果。
 *
 * 关键设计
 * --------
 * 1. 确定性：页面用固定种子的伪随机数生成点簇（mulberry32），
 *    同一姓同一期每次渲染的点位完全一致，因此可以逐帧复现。
 * 2. 动画可控：页面默认用 requestAnimationFrame 做生长动画。
 *    出片时把动画关闭、直接渲染终态静帧，保证每帧可复现、可重渲。
 * 3. 底图就绪判定：腾讯地图瓦片异步加载，脚本等到 canvas 出现且稳定后才截帧，
 *    否则会出现前几帧空白、后面才有底图的闪跳。
 *
 * 用法
 * ----
 * node render_frames.js                              # 全部已接入姓 × 五期
 * node render_frames.js --surnames 李,陈              # 指定姓
 * node render_frames.js --periods pre_qin,modern
 * node render_frames.js --out shots --fps 25 --scale 2
 * node render_frames.js --video                       # 截帧后直接合成 mp4
 */
const fs = require('fs');
const path = require('path');
const http = require('http');
const { execFileSync, spawnSync } = require('child_process');
const { chromium } = require('playwright');

const ROOT = __dirname;
const HTML = path.join(ROOT, 'index.html');
/* 史料层的朝代 id（带下划线）与页面 periods 数组的 id（无下划线）不同名，
 * 这里给出映射，避免 findIndex 落空后全部落到最后一期。 */
const PERIOD_MAP = {
  pre_qin: 'preqin', wei_jin: 'weijin', tang_song: 'tangsong',
  ming_qing: 'mingqing', modern: 'modern'
};
const PERIOD_IDS = Object.keys(PERIOD_MAP);

/* ---------- 参数 ---------- */
function parseArgs(argv) {
  const a = {
    surnames: '', periods: '', out: path.join(ROOT, 'shots'),
    fps: 25, scale: 2, width: 1920, height: 1080,
    video: false, noBase: false, keepBrowser: false, exportMode: true,
    hold: 500, server: '', path: ''
  };
  for (let i = 2; i < argv.length; i++) {
    const k = argv[i];
    const next = () => argv[++i];
    if (k === '--surnames') a.surnames = next();
    else if (k === '--periods') a.periods = next();
    else if (k === '--out') a.out = path.resolve(next());
    else if (k === '--fps') a.fps = +next();
    else if (k === '--scale') a.scale = +next();
    else if (k === '--width') a.width = +next();
    else if (k === '--height') a.height = +next();
    else if (k === '--video') a.video = true;
    else if (k === '--no-base') a.noBase = true;
    else if (k === '--keep-browser') a.keepBrowser = true;
    else if (k === '--ui') a.exportMode = false;
    else if (k === '--hold') a.hold = +next();
    else if (k === '--server') a.server = next();
    else if (k === '--path') a.path = next();
  }
  return a;
}

/* ---------- 找浏览器 ---------- */
function findChrome() {
  const localApp = process.env.LOCALAPPDATA ||
    (process.env.HOME ? path.join(process.env.HOME, '.local', 'share') : '');
  const pwRoot = localApp ? path.join(localApp, 'ms-playwright') : '';
  if (pwRoot && fs.existsSync(pwRoot)) {
    for (const d of fs.readdirSync(pwRoot)) {
      if (!d.startsWith('chromium')) continue;
      const cands = [
        path.join(pwRoot, d, 'chrome-win', 'chrome.exe'),
        path.join(pwRoot, d, 'chrome-win32', 'chrome.exe'),
        path.join(pwRoot, d, 'chrome-win', 'chrome.exe')
      ];
      for (const c of cands) if (fs.existsSync(c)) return c;
    }
  }
  const sys = [
    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
    'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
    'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe'
  ];
  for (const c of sys) if (fs.existsSync(c)) return c;
  return null;
}

/* ---------- ffmpeg ---------- */
function hasFfmpeg() {
  try {
    execFileSync('ffmpeg', ['-version'], { stdio: 'ignore' });
    return true;
  } catch (e) { return false; }
}

/* ---------- 静态服务 ----------
 * 腾讯地图 JS API 不支持 file:// 协议，必须走 http。
 * 但底图鉴权需要 WorkBuddy 的密钥代理（/_TMapService/_wbt/<secret>），
 * 该代理只存在于 WorkBuddy 预览服务器上。
 * 因此默认连预览服务器的静态托管路径：
 *   --server http://127.0.0.1:44794
 *   --path   /static-html/<hash>/index.html
 * 若都不给，则退回自建服务（无底图模式，仅供调试，不可发布）。
 */
const MIME = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8', '.css': 'text/css; charset=utf-8',
  '.png': 'image/png', '.jpg': 'image/jpeg', '.svg': 'image/svg+xml'
};
function startServer(root) {
  return new Promise((resolve, reject) => {
    const srv = http.createServer((req, res) => {
      let p = decodeURIComponent(req.url.split('?')[0]);
      if (p === '/') p = '/index.html';
      const f = path.join(root, p);
      if (!f.startsWith(root) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) {
        res.writeHead(404); res.end('not found'); return;
      }
      res.writeHead(200, { 'Content-Type': MIME[path.extname(f).toLowerCase()] || 'application/octet-stream' });
      fs.createReadStream(f).pipe(res);
    });
    srv.on('error', reject);
    srv.listen(0, '127.0.0.1', () => resolve({ srv, port: srv.address().port }));
  });
}

/* 在预览服务器里找出当前项目的静态托管路径（含密钥替换） */
async function findPreviewPath(port) {
  const res = await fetch('http://127.0.0.1:' + port + '/static-html/');
  if (!res.ok) return null;
  const html = await res.text();
  const m = html.match(/href="([^"]*index\.html)"/);
  return m ? m[1] : null;
}

/* ---------- 主流程 ---------- */
(async () => {
  const args = parseArgs(process.argv);

  if (!fs.existsSync(HTML)) {
    console.log('✗ 找不到 index.html，请先运行 python build.py');
    process.exit(2);
  }

  // 已接入的姓
  let allChars = [];
  const genPath = path.join(ROOT, 'genealogy.json');
  if (fs.existsSync(genPath)) {
    allChars = Object.keys(JSON.parse(fs.readFileSync(genPath, 'utf8')).surnames || {});
  }
  const chars = args.surnames ? args.surnames.split(',').map(s => s.trim()).filter(Boolean) : allChars;
  const periods = args.periods ? args.periods.split(',').map(s => s.trim()).filter(Boolean) : PERIOD_IDS;
  if (!chars.length) {
    console.log('✗ 没有可出片的姓（史料层尚未接入任何姓）');
    process.exit(2);
  }

  const exe = findChrome();
  console.log('浏览器：' + (exe || '未找到'));
  if (!exe) {
    console.log('✗ 未找到可用的 Chromium/Edge/Chrome。');
    console.log('  可执行：npx playwright install chromium');
    process.exit(2);
  }

  fs.mkdirSync(args.out, { recursive: true });
  const shots = [];
  const errors = [];
  const t0 = Date.now();

  const browser = await chromium.launch({
    executablePath: exe,
    headless: true,
    args: [
      '--disable-gpu', '--no-sandbox', '--disable-dev-shm-usage',
      '--allow-file-access-from-files', '--ignore-certificate-errors',
      '--hide-scrollbars', '--mute-audio'
    ]
  });
  const ctx = await browser.newContext({
    viewport: { width: args.width, height: args.height },
    deviceScaleFactor: args.scale
  });
  const page = await ctx.newPage();
  page.on('pageerror', e => errors.push('pageerror: ' + e.message));
  page.on('console', m => { if (m.type() === 'error') errors.push('console.error: ' + m.text()); });

  /* 决定页面地址：
     优先连 WorkBuddy 预览服务器（底图密钥代理可用，出片可发布）；
     否则退回自建服务（无底图，仅调试）。 */
  let pageUrl = null, srv = null;
  if (args.server) {
    /* 规范化：允许写 44794 / http://127.0.0.1:44794 / http://127.0.0.1:44794/ */
    let base = String(args.server).trim();
    if (!/^https?:\/\//i.test(base)) base = 'http://127.0.0.1:' + base.replace(/\/+$/, '');
    base = base.replace(/\/+$/, '');
    if (args.path) {
      pageUrl = base + (args.path.startsWith('/') ? args.path : '/' + args.path);
    } else {
      const p = await findPreviewPath(base);
      if (p) pageUrl = base + p;
    }
    if (pageUrl) console.log('加载页面（WorkBuddy 预览服务，底图可用）：' + pageUrl);
    else console.log('⚠ 预览服务未找到静态托管路径，改用自建服务（无底图）');
  }
  if (!pageUrl) {
    const started = await startServer(ROOT);
    srv = started.srv;
    pageUrl = 'http://127.0.0.1:' + started.port + '/index.html';
    console.log('加载页面（自建服务，无底图）：' + pageUrl);
    console.log('  提示：出可发布的片请加 --server <WorkBuddy预览端口> [--path <托管路径>]');
  }
  await page.goto(pageUrl, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(3000);

  const ready = await page.evaluate(() => !!(window.__atlas && window.__atlas.state));
  console.log('页面状态：' + (ready ? '已就绪' : '未就绪（可能无底图）'));
  if (!ready) {
    await browser.close();
    console.log('✗ 页面未初始化，无法出片。');
    process.exit(3);
  }

  // 出片模式：隐藏品牌/图例/侧栏/说明，只留画面与字幕
  if (args.exportMode) {
    await page.evaluate(() => {
      const btn = document.getElementById('btnExportMode');
      if (btn && !document.getElementById('app').classList.contains('export')) btn.click();
      else document.getElementById('app').classList.add('export');
      document.getElementById('app').classList.add('export');
    });
    await page.waitForTimeout(600);
  }
  if (args.noBase) {
    await page.evaluate(() => { window.__atlas.setBase(false); });
  }

  // 等待底图 canvas 与瓦片稳定
  try {
    await page.waitForFunction(
      () => { const m = document.getElementById('map'); return m && m.querySelector('canvas'); },
      { timeout: 20000 });
    await page.waitForTimeout(4000);
    console.log('底图已就绪');
  } catch (e) {
    console.log('⚠ 底图 canvas 未出现，将是无底图模式（不可用于发布）');
  }

  for (const ch of chars) {
    const ok = await page.evaluate((c) => {
      const a = window.__atlas;
      const i = a.surnames().findIndex(s => s.char === c);
      if (i < 0) return false;
      a.setStyle('spread');
      a.setSurname(i);
      a.setAnim(false);
      return true;
    }, ch);
    if (!ok) { console.log('⚠ 跳过 ' + ch + '（页面未接入该姓）'); continue; }
    await page.waitForTimeout(350);

    for (const pid of periods) {
      const ok = await page.evaluate((p) => {
        const a = window.__atlas;
        const ps = a.periods();
        let i = ps.findIndex(x => x.id === p);
        if (i < 0) {
          /* 找不到精确 id 就按标签匹配，再不行才落到最后一期 */
          i = ps.findIndex(x => (x.label || '').indexOf(p) >= 0);
        }
        if (i < 0) return false;
        a.setPeriod(i);
        a.setAnim(false);
        return true;
      }, PERIOD_MAP[pid] || pid);
      if (!ok) { console.log('⚠ 跳过 ' + ch + '/' + pid + '（未找到该朝代）'); continue; }
      await page.waitForTimeout(args.hold);

      const d = path.join(args.out, ch);
      fs.mkdirSync(d, { recursive: true });
      const f = path.join(d, pid + '.png');
      await page.screenshot({ path: f });
      shots.push(f);
      console.log('  ✓ ' + ch + ' / ' + pid + ' → ' + path.relative(ROOT, f));
    }
  }

  if (!args.keepBrowser) await browser.close();
  if (srv) srv.close();

  console.log('');
  console.log('共 ' + shots.length + ' 张，耗时 ' + ((Date.now() - t0) / 1000).toFixed(1) + ' 秒');

  /* 出片校验：逐帧比对文件哈希，确保每帧确实不同。
     曾出现过「朝代 id 写错 → findIndex 落空 → 全部渲染最后一期」，
     结果每期截图一模一样，肉眼很难发现，故在此硬校验。 */
  const crypto = require('crypto');
  const seen = new Map();
  let dup = 0;
  shots.forEach(f => {
    const h = crypto.createHash('md5').update(fs.readFileSync(f)).digest('hex');
    if (seen.has(h)) { dup++; console.log('  ⚠ 内容重复：' + path.basename(f) + ' 与 ' + path.basename(seen.get(h))); }
    else seen.set(h, f);
  });
  if (dup) console.log('✗ 有 ' + dup + ' 张重复帧，请检查朝代 id 映射');
  else console.log('✓ ' + shots.length + ' 帧内容互不相同');

  if (errors.length) {
    console.log('页面错误 ' + errors.length + ' 条：');
    errors.slice(0, 8).forEach(e => console.log('   ' + e));
  }

  // ffmpeg 合成：先把每个姓的五期静帧按顺序拼成一段，再把各姓段接起来
  if (args.video && shots.length) {
    if (!hasFfmpeg()) {
      console.log('✗ 未找到 ffmpeg，跳过合成。');
    } else {
      const mp4 = path.join(args.out, 'surname_atlas.mp4');
      console.log('合成视频：' + mp4);
      const tmp = path.join(args.out, '_seq');
      fs.rmSync(tmp, { recursive: true, force: true });
      fs.mkdirSync(tmp, { recursive: true });

      // 为每个姓×期生成一个 1 帧的序列片段，用 concat 拼接
      const listFile = path.join(args.out, '_concat.txt');
      const parts = [];
      let idx = 0;
      for (const ch of chars) {
        for (const pid of periods) {
          const src = path.join(args.out, ch, pid + '.png');
          if (!fs.existsSync(src)) continue;
          const part = path.join(tmp, ('p' + idx).padStart(4, '0') + '.png');
          fs.copyFileSync(src, part);
          parts.push(part);
          idx++;
        }
      }
      // concat demuxer 要求同目录且同名序列
      const seqTxt = path.join(tmp, 'seq.txt');
      fs.writeFileSync(seqTxt, parts.map(p => "file '" + p.replace(/\\/g, '/') + "'").join('\n'),
        'utf8');
      const r = spawnSync('ffmpeg', [
        '-y', '-f', 'concat', '-safe', '0', '-i', seqTxt,
        '-vf', 'scale=' + args.width + ':' + args.height + ',fps=' + args.fps,
        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-r', String(args.fps), mp4
      ], { encoding: 'utf8' });
      if (r.status !== 0) {
        console.log('✗ ffmpeg 失败：\n' + (r.stderr || '').slice(-1500));
      } else {
        console.log('✓ 已生成 ' + mp4);
      }
      fs.rmSync(tmp, { recursive: true, force: true });
      if (fs.existsSync(listFile)) fs.rmSync(listFile);
    }
  }
  process.exit(0);
})().catch(e => { console.error('出片失败：', e); process.exit(1); });
