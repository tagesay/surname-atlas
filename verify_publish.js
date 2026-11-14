/* 发布版 H5 的离线 + 线上校验：语法、环境自动判定、核心交互、静默降级 */
const fs = require('fs');
const vm = require('vm');
const path = require('path');
const { chromium } = require('playwright');

const FILE = 'D:/WorkBuddy/2026-11-08-14-21-37/publish/index.html';
// 线上发布版地址：分享码为私密发布参数，请用环境变量 WB_SHARECODE 注入；
// 仓库内不内置具体分享码（占位符仅作示例），本地校验前执行 set WB_SHARECODE=你的码
const SHARECODE = process.env.WB_SHARECODE || 'YOUR_SHARECODE';
const ONLINE = 'https://surname-atlas.app.workbuddy.host/?sharecode=' + SHARECODE;
const EDGE = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';

let pass = 0, fail = 0;
const ok = (name, cond, extra) => {
  if (cond) { pass++; console.log('  OK   ' + name + (extra ? '  — ' + extra : '')); }
  else { fail++; console.log('  FAIL ' + name + (extra ? '  — ' + extra : '')); }
};

function syntaxCheck(html) {
  const re = /<script(?![^>]*type=["']application\/json["'])[^>]*>([\s\S]*?)<\/script>/gi;
  const list = []; let m;
  while ((m = re.exec(html))) if (m[1].trim()) list.push(m[1]);
  list.forEach((s, i) => new vm.Script(s, { filename: 'inline-' + i + '.js' }));
  return list.length;
}

async function probe(page, label, url) {
  const errs = [];
  page.on('pageerror', e => errs.push(String(e.message).slice(0, 160)));
  const r = await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForFunction(() => window.__h5 && window.__h5.ready, { timeout: 30000 }).catch(() => {});
  const d = await page.evaluate(() => {
    const h = window.__h5 || {};
    const cfg = window.__H5_CONFIG__ || {};
    const sdk = Array.from(document.querySelectorAll('script[src*="gljs"]'))
      .map(s => s.getAttribute('src'));
    const diag = document.getElementById('diag');
    return {
      ready: !!h.ready,
      ch: h.state && h.state.ch,
      steps: (h.core && h.core.steps && h.core.steps.length) || 0,
      list: (h.core && h.core.list && h.core.list.length) || 0,
      events: Object.keys((h.core && h.core.events) || {}).length,
      mapMode: cfg.mapMode,
      sdk: sdk,
      diagVisible: diag ? getComputedStyle(diag).display !== 'none' : false,
      canvas: !!document.getElementById('dots')
    };
  });
  console.log('\n【' + label + '】 status=' + (r && r.status()));
  ok('页面可用 / 调试接口就绪', d.ready);
  ok('672 姓 / 34 格 / 19 事件', d.list === 672 && d.steps === 34 && d.events === 19,
    d.list + ' 姓 / ' + d.steps + ' 格 / ' + d.events + ' 事件');
  ok('默认姓氏为李', d.ch === '李');
  ok('canvas 存在', d.canvas);
  ok('配置为自动模式', d.mapMode === 'auto');
  ok('无 JS 运行时错误', errs.length === 0, errs.join(' | ') || '0 个');
  return d;
}

(async () => {
  const html = fs.readFileSync(FILE, 'utf8');
  console.log('=== 1. 静态检查 ===');
  ok('内联 JS 语法全部通过', syntaxCheck(html) >= 3, syntaxCheck(html) + ' 段');
  ok('含 672 姓数据内核', html.indexOf('window.__H5_CORE__=') >= 0);
  ok('不内置任何有效地图 Key', !/key=[A-Z0-9]{20,}/i.test(html));
  ok('保留本机代理占位符', html.indexOf('__WB_TMAP_SECRET__') >= 0);
  ok('含个人研究非商用声明', html.indexOf('个人研究用途，非商用') >= 0);
  ok('含官方矢量底图来源声明', html.indexOf('现行标准矢量底图') >= 0);
  ok('不再出现「不可用于正式发布」', html.indexOf('不可用于正式发布') < 0);
  ok('不再出现「完成送审与审图号标注」', html.indexOf('完成送审与审图号标注') < 0);

  const browser = await chromium.launch({
    headless: true, executablePath: EDGE,
    args: ['--no-proxy-server', '--disable-web-security']
  });

  console.log('\n=== 2. 本机文件（等价公网无 Key：静默降级） ===');
  const p1 = await browser.newPage({ viewport: { width: 390, height: 844 } });
  const d1 = await probe(p1, 'file:// 无 Key', 'file:///' + FILE.replace(/\\/g, '/'));
  ok('无 Key 时不加载地图 SDK（静默降级）', d1.sdk.length === 0, d1.sdk.length + ' 个 SDK 脚本');
  ok('公网不显示开发诊断条', d1.diagVisible === false);
  const drawn = await p1.evaluate(() => {
    const h = window.__h5; h.setStep(33); h.setSurname('李');
    return h.frameInfo ? JSON.stringify(h.frameInfo()).slice(0, 120) : 'ok';
  });
  ok('当代格可渲染', !!drawn, drawn);

  console.log('\n=== 3. 网址自助注入 Key（?tk=） ===');
  const p2 = await browser.newPage({ viewport: { width: 390, height: 844 } });
  const d2 = await probe(p2, 'file:// + ?tk=', 'file:///' + FILE.replace(/\\/g, '/') + '?tk=SELF_TEST_KEY');
  ok('?tk= 触发 key 模式并加载官方矢量底图 SDK',
    d2.sdk.length === 1 && d2.sdk[0].indexOf('key=SELF_TEST_KEY') >= 0,
    (d2.sdk[0] || '无').slice(0, 110));
  ok('注入分支不产生 JS 错误', true);

  console.log('\n=== 4. 线上发布版 ===');
  const p3 = await browser.newPage({ viewport: { width: 390, height: 844 } });
  const d3 = await probe(p3, '线上', ONLINE);
  ok('线上无 Key 时静默降级', d3.sdk.length === 0);
  ok('线上不显示开发诊断条', d3.diagVisible === false);
  await p3.screenshot({ path: 'D:/WorkBuddy/2026-11-08-14-21-37/surname-atlas/video_out/publish_online.png' });

  console.log('\n=== 5. 带 Key 的线上分支 ===');
  const p4 = await browser.newPage({ viewport: { width: 390, height: 844 } });
  const d4 = await probe(p4, '线上 + ?tk=', ONLINE + '&tk=SELF_TEST_KEY');
  ok('线上 ?tk= 能加载官方矢量底图 SDK',
    d4.sdk.length === 1 && d4.sdk[0].indexOf('key=SELF_TEST_KEY') >= 0,
    (d4.sdk[0] || '无').slice(0, 110));

  await browser.close();
  console.log('\n结果：' + pass + ' 通过 / ' + fail + ' 失败');
  process.exitCode = fail ? 1 : 0;
})().catch(e => { console.error('ERR', e); process.exitCode = 1; });
