/* 34 格共用百年时间轴 · 纯可视化批量出片
 *
 * 与旧的 render_frames.js（5 期静帧）不同：
 *   · 页面是 cinema.html，34 格时间轴，无口播、无字幕、无图例、无侧栏
 *   · 每格之间做帧间插值（__atlas.setProgress(浮点格位)），点簇逐点渐显 / 渐隐，
 *     得到真正连续的「繁衍 / 扩散 / 凋零」过程，而不是 34 张跳变的静图
 *   · 多个姓串成一条片子，姓与姓之间用点密度淡出淡入衔接
 *   · 所有帧写入单一连续编号序列，ffmpeg 一次合成；逐帧 MD5 校验防重复帧
 *
 * 用法
 * ----
 * node render_century.js --surnames 李 --subframes 4 --quick   # 快速自检
 * node render_century.js --video                              # 全量出片
 * node render_century.js --server http://127.0.0.1:44794 \
 *      --path /static-html/<hash>/cinema.html --video
 */
const fs = require('fs');
const path = require('path');
const http = require('http');
const { execFileSync, spawnSync } = require('child_process');
const { chromium } = require('playwright');

const ROOT = __dirname;
const DEFAULT_PATH = '/static-html/d3f5dce7cb51a486/cinema.html';
const DEFAULT_SERVER = 'http://127.0.0.1:44794';

function parseArgs(argv) {
  const a = {
    surnames: '', subframes: 8, fps: 24, scale: 1, width: 1280, height: 720,
    out: path.join(ROOT, 'frames'), video: false, events: true, hud: true,
    server: DEFAULT_SERVER, path: DEFAULT_PATH, hold: 0,
    transition: 6, endHold: 20, quick: false, steps: '', stills: true,
    pace: 'slow-early', overlay: false,
    // 有事件的世纪额外停留，供观众读右下角的事件标注。
    // 停留帧用硬链接复制同一张 PNG，不重新截图，所以几乎不增加渲染时间。
    holdEvents: true, holdBase: 24, holdExtra: 12
  };
  for (let i = 2; i < argv.length; i++) {
    const k = argv[i], next = () => argv[++i];
    if (k === '--surnames') a.surnames = next();
    else if (k === '--subframes') a.subframes = +next();
    else if (k === '--fps') a.fps = +next();
    else if (k === '--scale') a.scale = +next();
    else if (k === '--width') a.width = +next();
    else if (k === '--height') a.height = +next();
    else if (k === '--out') a.out = path.resolve(next());
    else if (k === '--video') a.video = true;
    else if (k === '--events') a.events = true;
    else if (k === '--no-events') a.events = false;
    else if (k === '--no-hud') a.hud = false;
    else if (k === '--server') a.server = next();
    else if (k === '--path') a.path = next();
    else if (k === '--hold') a.hold = +next();
    else if (k === '--transition') a.transition = +next();
    else if (k === '--end-hold') a.endHold = +next();
    else if (k === '--quick') a.quick = true;
    else if (k === '--steps') a.steps = next();
    else if (k === '--no-stills') a.stills = false;
    else if (k === '--pace') a.pace = next();
    else if (k === '--overlay') a.overlay = true;
    else if (k === '--no-hold-events') a.holdEvents = false;
    else if (k === '--hold-base') a.holdBase = +next();
    else if (k === '--hold-extra') a.holdExtra = +next();
  }
  return a;
}

/* 时间轴采样点。默认 slow-early：起源与早期世纪走慢一点（点少、需要看清楚），
   唐宋以后尤其是明清—近现代事件密集，节奏加快，形成「平缓 → 激昂」的视觉推进。
   uniform 则每格等长。 */
function timelinePoints(from, to, baseSf, mode) {
  const pts = [];
  for (let i = from; i < to; i++) {
    const sf = (mode === 'slow-early')
      ? Math.max(1, Math.round(baseSf * (i < 16 ? 1.6 : 1)))
      : baseSf;
    for (let k = 0; k < sf; k++) {
      pts.push({ t: i + k / sf, step: i, key: k === 0, last: k === sf - 1 });
    }
  }
  pts.push({ t: to, step: to, key: true, last: true });
  return pts;
}

function findChrome() {
  const localApp = process.env.LOCALAPPDATA ||
    (process.env.HOME ? path.join(process.env.HOME, '.local', 'share') : '');
  const pwRoot = localApp ? path.join(localApp, 'ms-playwright') : '';
  if (pwRoot && fs.existsSync(pwRoot)) {
    for (const d of fs.readdirSync(pwRoot)) {
      if (!d.startsWith('chromium')) continue;
      for (const c of [path.join(pwRoot, d, 'chrome-win', 'chrome.exe'),
                       path.join(pwRoot, d, 'chrome-win32', 'chrome.exe')]) {
        if (fs.existsSync(c)) return c;
      }
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

const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8', '.png': 'image/png' };
function startServer(root) {
  return new Promise((resolve, reject) => {
    const srv = http.createServer((req, res) => {
      let p = decodeURIComponent(req.url.split('?')[0]);
      if (p === '/') p = '/cinema.html';
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

function hasFfmpeg() {
  try { execFileSync('ffmpeg', ['-version'], { stdio: 'ignore' }); return true; }
  catch (e) { return false; }
}

(async () => {
  const args = parseArgs(process.argv);
  const ca = JSON.parse(fs.readFileSync(path.join(ROOT, 'century_atlas.json'), 'utf8'));
  const allChars = Object.keys(ca.surnames || {});
  const chars = args.surnames
    ? args.surnames.split(',').map(s => s.trim()).filter(Boolean)
    : allChars;
  const N = ca.steps.length;
  if (!chars.length) { console.log('✗ 没有可出片的姓'); process.exit(2); }

  // 快速自检只跑少量帧，便于先确认页面、底图、投影、绘图链路
  let tFrom = 0, tTo = N - 1;
  if (args.steps) {
    const m = String(args.steps).match(/^(\d+)\s*-\s*(\d+)$/);
    if (m) { tFrom = +m[1]; tTo = Math.min(N - 1, +m[2]); }
  }
  if (args.quick) {
    args.subframes = 3; args.transition = 2; args.endHold = 2;
    args.holdEvents = false; tTo = Math.min(tTo, 5);
  }

  const exe = findChrome();
  if (!exe) { console.log('✗ 未找到 Chromium/Edge。可执行 npx playwright install chromium'); process.exit(2); }

  const seqDir = path.join(args.out, 'seq');
  const stillDir = path.join(args.out, 'stills');
  fs.mkdirSync(seqDir, { recursive: true });
  if (args.stills) fs.mkdirSync(stillDir, { recursive: true });
  // 清空旧序列，避免上一轮残留混进新片。
  // 叠加总览只写 out/overlay/，不碰主片序列（Windows 逐文件删 3000 张 PNG 极慢，
  // 且会误删刚出好的帧序列）；每帧写盘时也会直接覆盖同名编号。
  if (!args.overlay) {
    fs.rmSync(seqDir, { recursive: true, force: true });
    fs.mkdirSync(seqDir, { recursive: true });
  }

  let srv = null, pageUrl = null;
  if (args.server && args.path) {
    let base = String(args.server).trim();
    if (!/^https?:\/\//i.test(base)) base = 'http://127.0.0.1:' + base.replace(/\/+$/, '');
    base = base.replace(/\/+$/, '');
    const candidate = base + (args.path.startsWith('/') ? args.path : '/' + args.path);
    try {
      const r = await fetch(candidate, { signal: AbortSignal.timeout(20000) });
      const txt = await r.text();
      if (r.ok && txt.indexOf('atlas-century') >= 0 && txt.indexOf('__WB_TMAP_SECRET__') < 0) {
        pageUrl = candidate;
        console.log('加载页面（预览服务 · 底图密钥代理可用）：' + pageUrl);
      } else {
        console.log('⚠ 预览服务上的 cinema.html 不可用（状态 ' + r.status + '），改用本地服务');
      }
    } catch (e) { console.log('⚠ 预览服务不可达：' + e.message + '，改用本地服务'); }
  }
  if (!pageUrl) {
    const started = await startServer(ROOT);
    srv = started.srv;
    pageUrl = 'http://127.0.0.1:' + started.port + '/cinema.html';
    console.log('加载页面（本地服务 · 无密钥代理，底图可能不可用；仅供调试）');
  }

  const browser = await chromium.launch({
    executablePath: exe, headless: true,
    args: ['--disable-gpu', '--no-sandbox', '--disable-dev-shm-usage',
           '--ignore-certificate-errors', '--hide-scrollbars', '--mute-audio']
  });
  const ctx = await browser.newContext({
    viewport: { width: args.width, height: args.height }, deviceScaleFactor: args.scale
  });
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push('pageerror: ' + e.message));
  page.on('console', m => { if (m.type() === 'error') errors.push('console.error: ' + m.text()); });

  await page.goto(pageUrl, { waitUntil: 'domcontentloaded', timeout: 120000 });
  await page.waitForTimeout(2500);
  const ready = await page.evaluate(() => !!(window.__atlas && window.__atlas.ready));
  if (!ready) { console.log('✗ cinema.html 未初始化'); await browser.close(); process.exit(3); }

  // 底图瓦片稳定后再截帧，避免开头几帧空白
  let mapOk = false;
  try {
    await page.waitForFunction(() => {
      const m = document.getElementById('map');
      return !!(m && m.querySelector('canvas'));
    }, { timeout: 20000 });
    await page.waitForTimeout(4000);
    mapOk = await page.evaluate(() => window.__atlas.mapReady);
  } catch (e) { /* 无底图，继续但会提示 */ }
  console.log('底图状态：' + (mapOk ? '已就绪' : '未就绪（画面不可用于发布，请先确认预览服务）'));

  await page.evaluate((a) => {
    window.__atlas.setAnim(false);
    window.__atlas.setHud(a.hud);
    window.__atlas.setEvents(a.events);
    window.__atlas.setBase(true);
  }, { hud: args.hud, events: args.events });

  /* 十姓叠加总览：全部姓同色画在同一张底图上，验证「多姓非排他、可铺满全国」。
     只输出几张关键年代静图，不参与主片序列。 */
  if (args.overlay) {
    const dir = path.join(args.out, 'overlay');
    fs.mkdirSync(dir, { recursive: true });
    await page.evaluate(() => window.__atlas.setOverlay(window.__atlas.surnames));
    for (const step of [2, 3, 16, 20, 26, 29, 31, 33]) {
      await page.evaluate(s => window.__atlas.setProgress(s), step);
      await page.waitForTimeout(150);
      await page.screenshot({ path: path.join(dir, 'step_' + String(step).padStart(2, '0') + '.png') });
      console.log('  ✓ 十姓叠加 step_' + String(step).padStart(2, '0'));
    }
    await browser.close();
    if (srv) srv.close();
    process.exit(0);
  }

  let seqIdx = 0, shotCount = 0, holdCount = 0;
  const t0 = Date.now();
  const shots = [];   // 只存真正截图的帧，用于唯一画面校验

  async function shot(t, ch, fade, stillTag, stillCh) {
    const num = String(seqIdx++).padStart(6, '0');
    const file = path.join(seqDir, num + '.png');
    await page.evaluate((p) => {
      const a = window.__atlas;
      if (p.ch) a.setSurname(p.ch);
      a.state.fade = p.fade;
      a.setProgress(p.t);
    }, { t, ch, fade });
    if (args.hold) await page.waitForTimeout(args.hold);
    // 强制等一帧绘制，避免截图落在 canvas 更新之前
    await page.evaluate(() => new Promise(r => requestAnimationFrame(() => r())));
    await page.screenshot({ path: file });
    shots.push(file);
    shotCount++;
    if (stillTag && args.stills) {
      const d = path.join(stillDir, stillCh || ch || 'x');
      fs.mkdirSync(d, { recursive: true });
      fs.copyFileSync(file, path.join(d, stillTag + '.png'));
    }
    if (shotCount % 100 === 0) {
      const sec = (Date.now() - t0) / 1000;
      console.log('  … 已截图 ' + shotCount + ' 张 / ' + (sec / shotCount).toFixed(2) + ' 秒每张');
    }
    return file;
  }

  /* 事件阅读停留：把该世纪最后一张画面重复若干帧。
     用硬链接（同卷、几乎零 IO），不重新截图、不重新渲染。
     事件越多停得越久：1 条 → holdBase 帧，每多 1 条再加 holdExtra 帧。 */
  function holdFrame(src, count) {
    for (let k = 0; k < count; k++) {
      const num = String(seqIdx++).padStart(6, '0');
      const dst = path.join(seqDir, num + '.png');
      try { fs.linkSync(src, dst); }
      catch (e) { fs.copyFileSync(src, dst); }
      holdCount++;
    }
  }

  const keySteps = new Set([0, 2, 3, 16, 20, 26, 29, 31, 32, 33].filter(s => s >= tFrom && s <= tTo));
  const caIndex = ca.surnames;

  for (let ci = 0; ci < chars.length; ci++) {
    const ch = chars[ci];
    console.log('[' + (ci + 1) + '/' + chars.length + '] ' + ch + ' 姓');
    const ok = await page.evaluate(c => window.__atlas.setSurname(c), ch);
    if (!ok) { console.log('  ⚠ 页面未接入该姓，跳过'); continue; }

    // 姓与姓之间：点密度淡出 → 切换 → 淡入，形成干净的段落分隔
    if (ci > 0) {
      for (let k = args.transition - 1; k >= 0; k--) await shot(tFrom, null, k / args.transition);
    }
    for (let k = 0; k < args.transition; k++) await shot(tFrom, ch, k / args.transition);

    const points = timelinePoints(tFrom, tTo, args.subframes, args.pace);
    for (const p of points) {
      const isKey = p.key && keySteps.has(p.step);
      const file = await shot(p.t, null, 1,
        isKey ? ('step_' + String(p.step).padStart(2, '0')) : null, ch);
      if (args.holdEvents && p.last) {
        const fr = (caIndex[ch] && caIndex[ch].frames[p.step]) || {};
        const evN = (fr.events || []).length;
        if (evN) holdFrame(file, args.holdBase + (evN - 1) * args.holdExtra);
      }
    }
    for (let k = 0; k < args.endHold; k++) await shot(tTo, null, 1);
  }

  await browser.close();
  if (srv) srv.close();

  const secs = (Date.now() - t0) / 1000;
  console.log('\n实际截图 ' + shotCount + ' 张 / 事件阅读停留帧 ' + holdCount +
    ' 张（硬链接）/ 序列共 ' + seqIdx + ' 帧');
  console.log('耗时 ' + secs.toFixed(1) + ' 秒（' + (secs / shotCount).toFixed(2) + ' 秒每张截图）');

  // 逐帧哈希校验：只对真正截图的帧做，停留帧是刻意重复，不计入
  const crypto = require('crypto');
  const files = shots;
  const seen = new Map(); let dup = 0;
  files.forEach(f => {
    const h = crypto.createHash('md5').update(fs.readFileSync(f)).digest('hex');
    if (seen.has(h)) { dup++; if (dup <= 6) console.log('  ⚠ 重复帧 ' + path.basename(f) + ' = ' + path.basename(seen.get(h))); }
    else seen.set(h, f);
  });
  // 过渡段与定格段本来就会重复，只有「完全相同且数量异常」才报警
  console.log('唯一画面 ' + seen.size + ' / 截图帧 ' + files.length +
    '（重复 ' + dup + ' 帧，含段间淡出/片尾定格；另有 ' + holdCount + ' 张事件阅读停留帧为刻意重复）');
  if (args.quick && seen.size < 5) console.log('✗ 自检失败：几乎没有不同画面，请检查 setProgress 是否生效');
  else console.log('✓ 画面序列随时间推进');

  if (errors.length) {
    console.log('页面错误 ' + errors.length + ' 条：');
    errors.slice(0, 6).forEach(e => console.log('   ' + e));
  }

  if (args.video) {
    if (!hasFfmpeg()) console.log('✗ 未找到 ffmpeg，PNG 序列已保留，可自行合成。');
    else {
      const mp4 = path.join(args.out, 'surname_century.mp4');
      console.log('合成视频：' + mp4);
      const r = spawnSync('ffmpeg', [
        '-y', '-framerate', String(args.fps), '-i', path.join(seqDir, '%06d.png'),
        '-c:v', 'libx264', '-preset', 'medium', '-crf', '18',
        '-pix_fmt', 'yuv420p', '-r', String(args.fps), '-movflags', '+faststart', mp4
      ], { encoding: 'utf8' });
      if (r.status !== 0) console.log('✗ ffmpeg 失败：\n' + (r.stderr || '').slice(-1400));
      else {
        const st = fs.statSync(mp4);
        console.log('✓ 已生成 ' + mp4 + '（' + (st.size / 1048576).toFixed(1) + ' MB / ' +
          (seqIdx / args.fps).toFixed(1) + ' 秒 / ' + args.fps + ' fps）');
      }
    }
  }
  process.exit(0);
})().catch(e => { console.error('出片失败：', e); process.exit(1); });
