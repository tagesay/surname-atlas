/* 微信公众号 JS-SDK 签名服务（最小可运行版，零第三方依赖）
 *
 * 为什么需要它：index.html 里的 wx.config 必须由服务端用 jsapi_ticket 对当前页面
 * URL 做 SHA1 签名；AppSecret 绝不能放进前端。本服务只做这一件事。
 *
 * 运行：
 *   set WX_APPID=wxXXXXXXXXXXXXXXXX
 *   set WX_APPSECRET=XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
 *   set ALLOW_HOST=your.domain.com
 *   node wx_sign_server.js
 * 然后把 index.html 顶部的 wxSignUrl 改成：
 *   wxSignUrl: 'https://your.domain.com/wx-sign'
 *
 * 公众号后台（mp.weixin.qq.com）需要同步配置：
 *   1. 设置与开发 → 公众号设置 → 功能设置
 *      · JS接口安全域名：your.domain.com（需放 MP_verify_xxx.txt 到根目录）
 *      · 网页授权域名：your.domain.com（本页不取 openid，可不配；配了更稳妥）
 *   2. 设置与开发 → 基本配置 → IP 白名单：把本服务出口 IP 加进去，
 *      否则拿 access_token 会报 40164。
 *   3. 已认证服务号/订阅号才有分享接口权限；未认证号 wx.config 会失败，
 *      页面会自动退回微信默认抓取的标题，功能演示不受影响。
 *
 * 部署要求：HTTPS、域名已 ICP 备案、证书有效。微信里不允许 http 的 JS-SDK 签名域名。
 */
'use strict';
const http = require('http');
const https = require('https');
const crypto = require('crypto');

const APPID = process.env.WX_APPID || '';
const SECRET = process.env.WX_APPSECRET || '';
const PORT = +(process.env.PORT || 8787);
const ALLOW_HOST = process.env.ALLOW_HOST || '';   // 只允许签本域名下的页面
const CORS_ORIGIN = process.env.CORS_ORIGIN || '*';

let tokenCache = { value: '', until: 0 };
let ticketCache = { value: '', until: 0 };

function getJSON(url) {
  return new Promise((resolve, reject) => {
    https.get(url, res => {
      let buf = '';
      res.setEncoding('utf8');
      res.on('data', d => buf += d);
      res.on('end', () => {
        try { resolve(JSON.parse(buf)); }
        catch (e) { reject(new Error('微信接口返回非 JSON：' + buf.slice(0, 160))); }
      });
    }).on('error', reject);
  });
}

async function accessToken() {
  if (tokenCache.value && Date.now() < tokenCache.until) return tokenCache.value;
  const d = await getJSON(
    'https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential'
    + '&appid=' + encodeURIComponent(APPID) + '&secret=' + encodeURIComponent(SECRET));
  if (!d.access_token) throw new Error('获取 access_token 失败：' + JSON.stringify(d));
  tokenCache = { value: d.access_token, until: Date.now() + (+(d.expires_in || 7200) - 300) * 1000 };
  return tokenCache.value;
}

async function jsapiTicket() {
  if (ticketCache.value && Date.now() < ticketCache.until) return ticketCache.value;
  const t = await accessToken();
  const d = await getJSON(
    'https://api.weixin.qq.com/cgi-bin/ticket/getticket?access_token='
    + encodeURIComponent(t) + '&type=jsapi');
  if (d.errcode !== 0 || !d.ticket) throw new Error('获取 jsapi_ticket 失败：' + JSON.stringify(d));
  ticketCache = { value: d.ticket, until: Date.now() + (+(d.expires_in || 7200) - 300) * 1000 };
  return ticketCache.value;
}

function send(res, code, obj) {
  const body = JSON.stringify(obj);
  res.writeHead(code, {
    'Content-Type': 'application/json; charset=utf-8',
    'Content-Length': Buffer.byteLength(body),
    'Access-Control-Allow-Origin': CORS_ORIGIN,
    'Access-Control-Allow-Headers': 'Content-Type',
    'Cache-Control': 'no-store'
  });
  res.end(body);
}

const server = http.createServer(async (req, res) => {
  const u = new URL(req.url, 'http://127.0.0.1');
  if (u.pathname === '/health') {
    return send(res, 200, { ok: true, appidConfigured: !!APPID,
      secretConfigured: !!SECRET, allowHost: ALLOW_HOST || '(未限制)' });
  }
  if (u.pathname !== '/wx-sign') return send(res, 404, { error: 'not found' });
  if (!APPID || !SECRET) return send(res, 503, { error: '服务端未配置 WX_APPID / WX_APPSECRET' });

  const url = u.searchParams.get('url') || '';
  if (!url) return send(res, 400, { error: '缺少 url 参数' });
  let host = '';
  try { host = new URL(url).hostname; } catch (e) { return send(res, 400, { error: 'url 非法' }); }
  if (ALLOW_HOST && host !== ALLOW_HOST && !host.endsWith('.' + ALLOW_HOST)) {
    return send(res, 403, { error: 'url 不在允许域名内：' + host });
  }

  try {
    const ticket = await jsapiTicket();
    const nonceStr = crypto.randomBytes(8).toString('hex');
    const timestamp = Math.floor(Date.now() / 1000);
    // 注意：参与签名的 url 必须是「去掉 # 及其后内容」的完整当前页地址，
    // 且参数顺序、大小写都不能变，否则微信校验会报 invalid signature。
    const raw = 'jsapi_ticket=' + ticket + '&noncestr=' + nonceStr
      + '&timestamp=' + timestamp + '&url=' + url;
    const signature = crypto.createHash('sha1').update(raw, 'utf8').digest('hex');
    send(res, 200, { appId: APPID, timestamp, nonceStr, signature, url });
  } catch (e) {
    send(res, 502, { error: String(e.message || e) });
  }
});

server.listen(PORT, () => {
  console.log('微信签名服务已启动：http://127.0.0.1:' + PORT + '/wx-sign');
  console.log('  AppID 已配置：' + (!!APPID) + ' / AppSecret 已配置：' + (!!SECRET));
  console.log('  允许域名：' + (ALLOW_HOST || '未限制（仅限本机调试）'));
  console.log('  自检：curl "http://127.0.0.1:' + PORT + '/health"');
  if (!APPID || !SECRET) console.log('  ⚠ 未配置凭据，/wx-sign 会返回 503，不会伪造签名。');
});
