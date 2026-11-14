/**
 * 小程序竖屏画面仿真预览
 *
 * 说明：本机没有可交互桌面，微信开发者工具原生模拟器起不来。
 * 这个脚本用【同一份小程序数据 + 同一份 renderer.js + 同一份 WXSS】
 * 在浏览器里复刻页面，用来直观检查布局与点密度效果。
 * 它是仿真图，不是真机截图，不能替代开发者工具的原生预览。
 *
 *   node make_mp_preview.js
 */
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const SRC = 'D:/WeChatProjects/surname-atlas';
const MP = path.join(SRC, 'miniprogram');
const ROOT = __dirname;
const OUT_HTML = path.join(ROOT, 'preview_mp.html');
const SHOTS = path.join(ROOT, 'video_out', 'mp_preview');

function findChrome() {
  const la = process.env.LOCALAPPDATA || 'C:\\Users\\Administrator\\AppData\\Local';
  const pw = path.join(la, 'ms-playwright');
  if (fs.existsSync(pw)) {
    for (const d of fs.readdirSync(pw)) {
      for (const c of [path.join(pw, d, 'chrome-win', 'chrome.exe'),
                       path.join(pw, d, 'chrome-win32', 'chrome.exe')])
        if (fs.existsSync(c)) return c;
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

function cssFromWxss() {
  const app = fs.readFileSync(path.join(MP, 'app.wxss'), 'utf8');
  const idx = fs.readFileSync(path.join(MP, 'pages/index/index.wxss'), 'utf8');
  const raw = app + '\n' + idx;
  /* 390px 宽视口下 750rpx = 屏宽，近似 1rpx = 0.52px；这里用 0.5 便于对齐 */
  return raw.replace(/(\d*\.?\d+)rpx/g, (m, n) => (parseFloat(n) / 2) + 'px')
            .replace(/\/\*[\s\S]*?\*\//g, '');
}

function inject(file) {
  const src = fs.readFileSync(file, 'utf8').replace(/<\/script/gi, '<\\/script');
  return '(function(){var module={exports:{}};' + src + '\nreturn module.exports;})()';
}

const html = `<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>姓氏繁衍 · 小程序画面仿真</title>
<style>
  html,body{margin:0;padding:0;background:#F5F2EA;overflow:hidden}
  ${cssFromWxss()}
  .serif{font-family:'Songti SC','STSong','SimSun',serif}
  .num{font-family:'DIN Alternate',Baskerville,Georgia,serif}
  .btn{cursor:pointer}
</style></head><body>
<div class="page" id="page">
  <canvas id="dots" class="dots"></canvas>

  <div class="top">
    <div class="brand"><span class="bt serif">姓氏繁衍</span><span class="bid num">TigerFRM</span></div>
    <div class="pickbtn" id="pickbtn">选姓</div>
  </div>
  <div class="glyph serif" id="glyph">李</div>
  <div class="era" id="era"><div class="eraMain serif" id="eraMain"></div><div class="eraSub" id="eraSub"></div></div>
  <div class="lv" id="lv"></div>
  <div class="events" id="events" style="display:none"></div>

  <div class="ctrl">
    <div class="scrub" id="scrub"><div style="height:2px;margin-top:18px;background:rgba(24,33,44,.12)">
      <div id="scrubFill" style="height:100%;background:#E5342A;width:0%"></div></div></div>
    <div class="row">
      <div class="btn">‹</div><div class="btn primary">播放</div><div class="btn">›</div>
      <div class="btn" id="infobtn">依据</div><div class="sp"></div>
      <div class="cnt num" id="cnt"></div>
    </div>
  </div>

  <div class="sheet" id="picker" style="display:none">
    <div class="sh"><span class="sht serif">选一个姓</span><div class="sp"></div><div class="btn">关闭</div></div>
    <div class="sheetBody" id="pickerBody"></div>
  </div>
  <div class="sheet" id="info" style="display:none">
    <div class="sh"><span class="sht serif">依据与口径</span><div class="sp"></div><div class="btn">关闭</div></div>
    <div class="sheetBody" id="infoBody"></div>
  </div>
</div>

<script>
var C = ${inject(path.join(MP, 'data/atlas.js'))};
var R = ${inject(path.join(MP, 'utils/renderer.js'))};
var N = C.steps.length;
var q = new URLSearchParams(location.search);
var state = { ch: q.get('ch') || '李', step: +(q.get('step') || 33), panel: q.get('panel') || '' };
var rowMap = {}; C.list.forEach(function(r){ rowMap[r.c] = r; });
if (!rowMap[state.ch]) state.ch = '李';
var row = rowMap[state.ch];
var full = !!(C.fullMeta && C.fullMeta[state.ch]);

function tierOf(r){ if(!r || r.rank==null) return 'D';
  return r.rank<=100?'A':(r.rank<=300?'B':(r.rank<=600?'C':'D')); }
var tier = tierOf(row);

function buildFrames(ch, t){
  if (C.fullFrames && C.fullFrames[ch]) return C.fullFrames[ch];
  var base=(C.generic||{})[t]||[], out=base.map(function(f){return f.slice();});
  var extra=[], mp=(C.maxProv||{})[ch];
  if(mp!==undefined) extra.push([mp,28,0,2]);
  ((C.topProv||{})[ch]||[]).forEach(function(p){extra.push([p,22,0,1]);});
  if((C.twTop||[]).indexOf(ch)>=0) (C.twPoints||[]).forEach(function(p){extra.push([p,11,1,0]);});
  if(extra.length) for(var i=0;i<N;i++) if((C.steps[i].cs||0)>=20) out[i]=out[i].concat(extra);
  return out;
}
var frames = buildFrames(state.ch, tier);

function span(d){ if(!d||d.s===undefined) return '';
  function lab(c){ return c<0?('前'+Math.abs(c)+'世纪'):(c+'世纪'); }
  return d.s===d.e?lab(d.s):(lab(d.s)+'—'+lab(d.e)); }
function eventsAt(i){
  var ids;
  if(full) ids=(C.fullMeta[state.ch].events[i]||[]).slice();
  else {
    ids=((C.allEvents&&C.allEvents[i])||[]).filter(function(id){
      var d=C.events[id]; if(!d) return false;
      return d.sc==='all'||(Array.isArray(d.sc)&&d.sc.indexOf(state.ch)>=0);
    });
    if(tier==='D') ids=ids.filter(function(id){return id!=='ev_xiandai';});
  }
  ids.sort(function(a,b){
    var ta=(C.events[a]&&C.events[a].t==='A')?0:1, tb=(C.events[b]&&C.events[b].t==='A')?0:1;
    if(ta!==tb) return ta-tb;
    return ((C.events[a]&&C.events[a].s)||0)-((C.events[b]&&C.events[b].s)||0);
  });
  return ids.map(function(id){ var d=C.events[id]||{};
    return {id:id,name:d.n||id,span:span(d),tier:d.t||'B',brief:d.b||'',src:d.src||''}; });
}
function esc(s){ return String(s==null?'':s).replace(/[&<>"]/g,function(c){
  return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }

/* ---- Canvas：与小程序 render() 完全同一套调用 ---- */
var W = window.innerWidth, H = window.innerHeight;
var cv = document.getElementById('dots'), dpr = 2;
cv.width = W*dpr; cv.height = H*dpr;
cv.style.width = W+'px'; cv.style.height = H+'px';
var ctx = cv.getContext('2d'); ctx.scale(dpr,dpr);
var zoom = R.fitZoom(W,H);
R.drawBase(ctx, C.PL, W, H, zoom);
var list = R.interpolated(state.step, frames, N);
var drawn = R.drawSites(ctx, list, C.PL, state.ch, W, H, zoom);

/* ---- HUD ---- */
var st = C.steps[state.step]||{}, evs=eventsAt(state.step);
document.getElementById('glyph').textContent = state.ch;
if (row.cmp) document.getElementById('glyph').className='glyph serif cp';
document.getElementById('eraMain').textContent = st.mode==='origin'
  ? ((st.era||'').split(' · ')[0]||st.label||'') : (st.label||'');
document.getElementById('eraSub').textContent = st.dyn||'';
document.getElementById('lv').textContent = (full?'史 · 逐姓史料':(row.lv==='official'?'官 · 官方省级结论':'谱 · 通用示意'))
  + ' · ' + (C.tierLabel[tier]||'');
document.getElementById('cnt').textContent = String(state.step+1).padStart(2,'0')+' / '+N;
document.getElementById('scrubFill').style.width = (state.step/(N-1)*100)+'%';

var ep = document.getElementById('events');
if(evs.length){
  var h='<div class="evhd">迁徙事件 · 本世纪 · '+evs.length+' 条</div>';
  evs.forEach(function(e,ix){
    h+='<div class="ev'+(ix===0?' first':'')+'"><div class="evnm">'+esc(e.name)+'</div>'
      +'<div class="evyr">'+esc(e.span)+' · '+esc(e.tier)+' 级依据</div>'
      +(e.brief?'<div class="evbr">'+esc(e.brief)+'</div>':'')+'</div>';
  });
  ep.innerHTML=h; ep.style.display='block';
}

/* ---- 抽屉 ---- */
function grid(rows){
  return '<div class="grid">'+rows.map(function(r){
    return '<div class="sn'+(r.c===state.ch?' on':'')+(r.cmp?' cp':'')+'">'
      +(r.lv==='full'?'<span class="mk">史</span>':'')+esc(r.c)
      +'<span class="py">'+esc(r.py)+'</span></div>';
  }).join('')+'</div>';
}
if(state.panel==='picker'){
  document.getElementById('picker').style.display='flex';
  var hot=C.list.filter(function(r){return r.rank&&r.rank<=24;}).sort(function(a,b){return a.rank-b.rank;});
  var all=C.list.slice().sort(function(a,b){return (a.py||'zz')<(b.py||'zz')?-1:1;}).slice(0,72);
  document.getElementById('pickerBody').innerHTML =
    '<input class="search" placeholder="输入汉字 / 拼音 / 首字母，如 李、li、l" readonly>'
    +'<div class="sect">热门姓氏</div>'+grid(hot)
    +'<div class="sect">全部姓氏 · '+C.list.length+' 个（示意前 72 个）</div>'+grid(all)
    +'<div class="note">「史」= 有逐姓史料与可考发祥地；「官」= 有公安部系列省级结论；无标记 = 见《百家姓》或现代姓氏名录，采用共用迁徙骨架，不标专属发祥地。</div>';
}
if(state.panel==='info'){
  document.getElementById('info').style.display='flex';
  var cards=[], p=[];
  p.push(state.ch+' 姓 · '+(row.py||'')+(row.bjx?'　《百家姓》第 '+row.bjx+' 位':'')
    +(row.rank?'　现代常见姓氏第 '+row.rank+' 名':''));
  if(full){
    var o=(C.fullMeta[state.ch]||{}).origin||{};
    p.push('发祥地 / 得姓：'+(o.region||'')+'（'+(o.dynasty||'')+'）');
    if(o.basis) p.push(o.basis);
  } else {
    p.push('本姓目前没有逐姓地理史料，因此不标专属发祥地、不编造家谱出处。');
    if(!row.rank) p.push('未入现代常见 600 名：没有「31 省均有分布」的公开依据，因此近现代不做全国铺开。');
  }
  cards.push({h:state.ch+' 姓 · 依据等级',p:p,l:(row.ev||[])});
  cards.push({h:'本世纪事件出处',p:evs.length?[]:['这一格没有活跃迁徙事件。'],
    l:evs.map(function(e){return e.name+'（'+e.tier+' 级）：'+(e.src||'出处见 migration_events.json');})});
  cards.push({h:'这套演示怎么读',p:[
    '时间轴共 '+N+' 格：西周分封前 3 格粗步长只作起源示意，之后每 100 年一格直到当代。',
    '点数不是人口数，只表示聚居证据强度与延续世纪数。',
    '画面不画任何国界 / 省界 / 历史疆域，不做分省设色，不用箭头。'],l:[]});
  document.getElementById('infoBody').innerHTML = cards.map(function(c){
    return '<div class="infoCard"><div class="ic-h serif">'+esc(c.h)+'</div>'
      +c.p.map(function(x){return '<div class="ic-p">'+esc(x)+'</div>';}).join('')
      +c.l.map(function(x){return '<div class="ic-li">· '+esc(x)+'</div>';}).join('')+'</div>';
  }).join('');
}

window.__mpPreview = { ch:state.ch, step:state.step, tier:tier, full:full,
  drawn:drawn, eventCount:evs.length, events:evs.map(function(e){return e.id;}),
  zoom:zoom, W:W, H:H, panel:state.panel };
</script></body></html>`;

(async () => {
  fs.mkdirSync(SHOTS, { recursive: true });
  fs.writeFileSync(OUT_HTML, html, 'utf8');
  console.log('仿真页：' + OUT_HTML + '（' + (Buffer.byteLength(html) / 1024).toFixed(0) + ' KB）');

  const exe = findChrome();
  if (!exe) { console.log('✗ 未找到 Chromium/Edge'); process.exit(2); }
  const browser = await chromium.launch({
    executablePath: exe, headless: true,
    args: ['--disable-gpu', '--no-sandbox', '--disable-dev-shm-usage', '--hide-scrollbars']
  });

  const C = require(path.join(MP, 'data/atlas.js'));
  const step17 = C.steps.findIndex(s => s.cs === 17);
  const stepYimen = C.fullMeta['陈'].events.findIndex(a => a.indexOf('ev_yimen') >= 0);

  const cases = [
    { name: '01_李_17世纪_竖屏', ch: '李', step: step17, w: 390, h: 844 },
    { name: '02_李_当代_竖屏', ch: '李', step: 33, w: 390, h: 844 },
    { name: '03_福_当代_D档_竖屏', ch: '福', step: 33, w: 390, h: 844 },
    { name: '04_陈_义门陈氏_竖屏', ch: '陈', step: stepYimen, w: 390, h: 844 },
    { name: '05_选姓抽屉_竖屏', ch: '李', step: 33, panel: 'picker', w: 390, h: 844 },
    { name: '06_依据抽屉_竖屏', ch: '李', step: step17, panel: 'info', w: 390, h: 844 },
    { name: '07_李_当代_横屏', ch: '李', step: 33, w: 844, h: 390 }
  ];

  const fileUrl = 'file:///' + OUT_HTML.replace(/\\/g, '/');
  let pass = 0, fail = 0;
  for (const c of cases) {
    const ctx = await browser.newContext({
      viewport: { width: c.w, height: c.h }, deviceScaleFactor: 2,
      isMobile: true, hasTouch: true
    });
    const page = await ctx.newPage();
    const errs = [];
    page.on('pageerror', e => errs.push(e.message));
    const qs = '?ch=' + encodeURIComponent(c.ch) + '&step=' + c.step + (c.panel ? '&panel=' + c.panel : '');
    await page.goto(fileUrl + qs, { waitUntil: 'load' });
    await page.waitForFunction(() => !!window.__mpPreview, { timeout: 15000 });
    const info = await page.evaluate(() => window.__mpPreview);
    const out = path.join(SHOTS, c.name + '.png');
    await page.screenshot({ path: out });
    const okc = !errs.length && (c.panel || info.drawn > 0);
    okc ? pass++ : fail++;
    console.log((okc ? '  ✓ ' : '  ✗ ') + c.name
      + ' — 点 ' + info.drawn + ' / 事件 ' + info.eventCount
      + ' / ' + info.W + '×' + info.H + (errs.length ? ' / ERR ' + errs[0] : ''));
    await ctx.close();
  }
  await browser.close();
  console.log('\n仿真预览：' + pass + ' 通过 / ' + fail + ' 失败');
  console.log('截图目录：' + SHOTS);
  process.exitCode = fail ? 1 : 0;
})().catch(e => { console.error('生成失败：', e); process.exitCode = 1; });
