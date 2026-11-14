/* 公众号 H5 浏览器实测：竖屏优先、自选姓氏、34 格、事件全展示、分享配置。
   用法：node verify_h5.js [--server http://127.0.0.1:44794] [--path /static-html/<hash>/index.html]
*/
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const ROOT = __dirname;
const DEFAULT_SERVER = 'http://127.0.0.1:44794';
const DEFAULT_PATH = '/static-html/d3f5dce7cb51a486/index.html';
const SHOT_DIR = path.join(ROOT, 'video_out', 'h5');

function findChrome() {
  const la = process.env.LOCALAPPDATA || 'C:\\Users\\Administrator\\AppData\\Local';
  const pwRoot = path.join(la, 'ms-playwright');
  if (fs.existsSync(pwRoot)) {
    for (const d of fs.readdirSync(pwRoot)) {
      for (const c of [path.join(pwRoot, d, 'chrome-win', 'chrome.exe'),
                       path.join(pwRoot, d, 'chrome-win32', 'chrome.exe')]) {
        if (fs.existsSync(c)) return c;
      }
    }
  }
  for (const c of [
    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
    'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
    'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe'
  ]) if (fs.existsSync(c)) return c;
  return null;
}

(async () => {
  const args = process.argv.slice(2);
  let server = DEFAULT_SERVER, urlPath = DEFAULT_PATH;
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--server') server = args[++i];
    if (args[i] === '--path') urlPath = args[++i];
  }
  const url = server.replace(/\/+$/, '') + (urlPath.startsWith('/') ? urlPath : '/' + urlPath);
  const exe = findChrome();
  if (!exe) { console.log('✗ 未找到 Chromium/Edge'); process.exit(2); }

  // 预览服务应已把地图密钥占位符替换掉
  const html = await (await fetch(url)).text();
  const proxyReady = html.indexOf('__WB_TMAP_SECRET__') < 0;
  console.log('页面：' + url);
  console.log('  大小 ' + (Buffer.byteLength(html) / 1024).toFixed(0) + ' KB / 密钥代理占位符 '
              + (proxyReady ? '已替换' : '未替换（将降级为无底图）'));
  if (html.indexOf('__H5_CORE_JSON__') >= 0) { console.log('✗ 数据占位符未注入'); process.exit(2); }

  fs.mkdirSync(SHOT_DIR, { recursive: true });
  const browser = await chromium.launch({
    executablePath: exe, headless: true,
    args: ['--disable-gpu', '--no-sandbox', '--disable-dev-shm-usage',
           '--ignore-certificate-errors', '--hide-scrollbars', '--mute-audio']
  });
  const ctx = await browser.newContext({
    viewport: { width: 390, height: 844 }, deviceScaleFactor: 2,
    isMobile: true, hasTouch: true, userAgent:
      'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 MicroMessenger/8.0'
  });
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push('pageerror: ' + e.message));
  page.on('console', m => { if (m.type() === 'error') errors.push('console.error: ' + m.text()); });

  let pass = 0, fail = 0;
  const check = (name, cond, detail) => {
    if (cond) { pass++; console.log('  ✓ ' + name + (detail ? ' — ' + detail : '')); }
    else { fail++; console.log('  ✗ ' + name + (detail ? ' — ' + detail : '')); }
  };

  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 40000 });
  try { await page.waitForFunction(() => window.__h5 && window.__h5.ready, { timeout: 20000 }); }
  catch (e) { console.log('✗ __h5 未就绪'); console.log(errors.join('\n')); await browser.close(); process.exit(2); }
  await page.waitForTimeout(1800);   // 等底图 SDK 与瓦片

  console.log('\n[1] 数据与启动');
  const boot = await page.evaluate(() => {
    const b = {
      n: window.__h5.surnameCount, full: window.__h5.fullChars,
      ch: window.__h5.state.ch, mapReady: window.__h5.mapReady,
      drawn: window.__h5.drawn,
      title: document.title,
      brand: document.getElementById('brandId').textContent
    };
    window.__h5.setStep(33);
    b.drawnModern = window.__h5.drawn;
    window.__h5.setStep(0);
    return b;
  });
  check('姓氏清单 672 个', boot.n === 672, '实际 ' + boot.n);
  check('逐姓史料 10 个', boot.full.length === 10, boot.full.join(''));
  check('默认落在李姓', boot.ch === '李', boot.ch);
  check('公众号品牌 TigerFRM', boot.brand === 'TigerFRM', boot.brand);
  if (boot.mapReady) check('底图可用', true, '腾讯地图已就绪');
  else console.log('  ! 底图降级为无底图模式（预览代理不可用，仅影响截图观感，不影响功能判定）');
  check('起源格干净、当代格铺开', boot.drawn === 0 && boot.drawnModern > 100,
        '首格 ' + boot.drawn + ' 点 / 当代 ' + boot.drawnModern + ' 点');

  console.log('\n[2] 自选姓氏与等级');
  const cases = [
    { ch: '李', full: true, expectTier: 'A' },
    { ch: '陈', full: true, expectTier: 'A' },
    { ch: '欧阳', full: false, expectTier: 'B' },
    { ch: '嘎', full: false, expectTier: 'C' },
    { ch: '福', full: false, expectTier: 'D' }
  ];
  for (const c of cases) {
    const r = await page.evaluate(ch => {
      window.__h5.setSurname(ch, true);
      window.__h5.setStep(33);
      const f = window.__h5.frameInfo();
      const row = window.__h5.core.list.find(x => x.c === ch) || {};
      return { ok: window.__h5.state.ch === ch, full: f.full, tier: f.tier,
               sites: f.sites, rank: row.rank, bjx: row.bjx, events: f.events };
    }, c.ch);
    check(c.ch + ' 姓演示可用', r.ok && r.sites > 0,
          '等级 ' + r.tier + ' / 当代点位 ' + r.sites + ' / 史料 ' + (r.full ? '逐姓' : '通用')
          + ' / 排名 ' + (r.rank || '未入榜') + ' / 百家姓序 ' + (r.bjx || '—'));
    check(c.ch + ' 等级判定', r.full === c.full && r.tier === c.expectTier,
          'full=' + r.full + ' tier=' + r.tier);
  }

  console.log('\n[3] 事件全部展示、不折叠');
  await page.evaluate(() => { window.__h5.setSurname('李', true); window.__h5.setStep(29); });
  const ev29 = await page.evaluate(() => {
    const p = document.getElementById('eventPanel');
    return {
      api: window.__h5.eventsAt(29),
      dom: document.querySelectorAll('#eventPanel .ev').length,
      text: p.textContent,
      shown: p.style.display,
      scrollH: p.scrollHeight, clientH: p.clientHeight
    };
  });
  check('17 世纪 3 条事件全部展开', ev29.api.length === 3 && ev29.dom === 3,
        '接口 ' + ev29.api.length + ' 条 / DOM ' + ev29.dom + ' 条');
  check('3 条事件无需滚动即可看全', ev29.scrollH <= ev29.clientH + 2,
        '内容 ' + ev29.scrollH + 'px / 可视 ' + ev29.clientH + 'px');
  check('无「另有 N 条」折叠提示', ev29.text.indexOf('另有') < 0 && ev29.text.indexOf('折叠') < 0);
  check('事件含背景简介', ev29.text.indexOf('招民填川诏') >= 0 || ev29.text.indexOf('湖广填四川') >= 0);
  check('事件面板可见', ev29.shown === 'block');
  const overflow = await page.evaluate(() => {
    const bad = [];
    for (const ch of window.__h5.fullChars) {
      window.__h5.setSurname(ch, true);
      for (let i = 0; i < 34; i++) {
        window.__h5.setStep(i);
        const p = document.getElementById('eventPanel');
        if (p.style.display === 'block' && p.scrollHeight > p.clientHeight + 2) {
          bad.push(ch + '@' + i + ':' + (p.scrollHeight - p.clientHeight) + 'px');
        }
      }
    }
    return bad;
  });
  check('10 姓 × 34 格事件均无高度截断', overflow.length === 0,
        overflow.length ? overflow.slice(0, 6).join(' ') : '340 帧全部完整可见');
  await page.setViewportSize({ width: 375, height: 667 });
  await page.waitForTimeout(500);
  const short = await page.evaluate(() => {
    window.__h5.setSurname('李', true); window.__h5.setStep(29);
    const p = document.getElementById('eventPanel');
    return { sh: p.scrollHeight, ch: p.clientHeight, dom: p.querySelectorAll('.ev').length };
  });
  check('矮屏 375×667 三条事件也完整', short.sh <= short.ch + 2 && short.dom === 3,
        '内容 ' + short.sh + 'px / 可视 ' + short.ch + 'px');
  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForTimeout(400);

  console.log('\n[4] 专属事件不串姓 / D 档不冒用官方结论');
  const ex = await page.evaluate(() => {
    const s11 = window.__h5.core.steps.findIndex(s => s.cs === 11);
    window.__h5.setSurname('陈', true); window.__h5.setStep(s11);
    const a = window.__h5.eventsAt(s11);
    window.__h5.setSurname('王', true); window.__h5.setStep(s11);
    const b = window.__h5.eventsAt(s11);
    window.__h5.setSurname('福', true); window.__h5.setStep(33);
    const c = window.__h5.eventsAt(33);
    const panel = document.getElementById('eventPanel').style.display;
    return { a, b, c, panel, s11 };
  });
  const hasYimen = ex.a.some(id => id === 'ev_yimen');
  check('陈姓 11 世纪含「义门陈氏分庄」', hasYimen, '格 ' + ex.s11 + ' / ' + ex.a.join(','));
  check('王姓 11 世纪不含陈姓专属事件', !ex.b.some(id => id === 'ev_yimen'), ex.b.join(','));
  check('D 档当代不显示「31 省均有分布」', !ex.c.some(id => id === 'ev_xiandai'),
        '事件数 ' + ex.c.length + ' / 面板 ' + ex.panel);

  console.log('\n[5] 降速节奏与播放控制');
  const pace = await page.evaluate(() => {
    window.__h5.setSurname('李', true);
    const s = window.__h5.state;
    const base = 1250;
    const withEv = s.acc[30] - s.acc[29];
    const noEv = s.acc[1] - s.acc[0];
    return { total: s.totalMs, withEv, noEv, accLen: s.acc.length };
  });
  check('有事件的世纪停留更久', pace.withEv > pace.noEv,
        '事件格 ' + pace.withEv + 'ms / 普通格 ' + pace.noEv + 'ms');
  check('全片时长足以阅读事件', pace.total > 34 * 1250,
        '全片 ' + (pace.total / 1000).toFixed(1) + ' 秒');
  await page.evaluate(() => window.__h5.play());
  await page.waitForTimeout(300);
  const playing = await page.evaluate(() => window.__h5.state.playing);
  check('播放可启动', playing === true);
  await page.evaluate(() => window.__h5.stop());

  console.log('\n[6] 搜索与选择器');
  const sr = await page.evaluate(() => {
    window.__h5.openPicker();
    const a = window.__h5.search('li');
    const hasLi = !!document.querySelector('#allGrid [data-ch="李"]');
    const b = window.__h5.search('欧阳');
    const hasOY = !!document.querySelector('#allGrid [data-ch="欧阳"]');
    const c = window.__h5.search('l');
    const hot = document.getElementById('hotGrid').children.length;
    return { a, b, c, hot, hasLi, hasOY,
             open: document.getElementById('picker').classList.contains('open') };
  });
  check('选择器可打开', sr.open === true);
  check('热门姓氏 24 个', sr.hot === 24, '实际 ' + sr.hot);
  check('拼音 li 可检索到李', sr.a > 0 && sr.hasLi, '结果 ' + sr.a);
  check('汉字「欧阳」可检索', sr.b > 0 && sr.hasOY, '结果 ' + sr.b);
  check('首字母 l 可检索', sr.c > 0, '结果 ' + sr.c);
  await page.evaluate(() => document.getElementById('picker').classList.remove('open'));

  console.log('\n[7] 依据卡与分享');
  const info = await page.evaluate(() => {
    window.__h5.setSurname('福', true);
    const t1 = document.getElementById('infoBody').textContent;
    window.__h5.setSurname('李', true);
    const t2 = document.getElementById('infoBody').textContent;
    return { t1, t2, title: document.title };
  });
  check('通用姓明确声明不伪造发祥地', info.t1.indexOf('不标专属发祥地') >= 0);
  check('逐姓姓展示发祥地与来源', info.t2.indexOf('陇西') >= 0 || info.t2.indexOf('发祥地') >= 0);
  check('分享标题随姓氏更新', info.title.indexOf('李') >= 0, info.title);

  console.log('\n[8] 截图');
  const shots = [
    { name: '01_李_17世纪_竖屏.png', ch: '李', step: 29, w: 390, h: 844 },
    { name: '02_李_当代_竖屏.png', ch: '李', step: 33, w: 390, h: 844 },
    { name: '03_福_当代_D档_竖屏.png', ch: '福', step: 33, w: 390, h: 844 },
    { name: '04_李_当代_横屏.png', ch: '李', step: 33, w: 844, h: 390 }
  ];
  for (const s of shots) {
    await page.setViewportSize({ width: s.w, height: s.h });
    await page.evaluate(o => { window.__h5.setSurname(o.ch, true); window.__h5.setStep(o.step); }, s);
    await page.waitForTimeout(1100);
    await page.screenshot({ path: path.join(SHOT_DIR, s.name) });
    const d = await page.evaluate(() => window.__h5.drawn);
    console.log('  · ' + s.name + '（点位 ' + d + '）');
  }

  console.log('\n[8b] 横屏取景');
  await page.setViewportSize({ width: 844, height: 390 });
  await page.waitForTimeout(1300);
  const proj = await page.evaluate(() => {
    const w = window.__h5.project(35, 73), e = window.__h5.project(35, 135);
    let z = null;
    try { z = window.__h5.map && window.__h5.map.getZoom ? window.__h5.map.getZoom() : null; } catch (err) {}
    return { x0: w[0], x1: e[0], span: e[0] - w[0], screenW: innerWidth, zoom: z,
             drawn: window.__h5.drawn };
  });
  check('横屏中国东西两端都在屏内', proj.x0 > -30 && proj.x1 < proj.screenW + 30,
        '西端 x=' + proj.x0.toFixed(0) + ' / 东端 x=' + proj.x1.toFixed(0)
        + ' / 屏宽 ' + proj.screenW + ' / zoom ' + proj.zoom);
  check('横屏点位数与竖屏同量级', proj.drawn > 150, '横屏 ' + proj.drawn + ' 点');

  console.log('\n[9] 页面错误');
  const realErrors = errors.filter(e => e.indexOf('404') < 0 && e.indexOf('favicon') < 0);
  check('无 JS 运行时错误', realErrors.length === 0,
        realErrors.length ? realErrors.slice(0, 3).join(' | ') : '干净');
  if (errors.length) console.log('  （全部日志）' + errors.slice(0, 5).join(' | '));

  console.log('\n结果：%d 通过 / %d 失败', pass, fail);
  console.log('截图目录：' + SHOT_DIR);
  await browser.close();
  process.exit(fail ? 1 : 0);
})().catch(e => { console.error('✗ 验证脚本异常：' + (e.stack || e)); process.exit(2); });
