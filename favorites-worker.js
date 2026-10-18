/**
 * 收藏夹小服务（Cloudflare Worker + KV）
 *
 * 为什么需要它：微信里打开的推送页面把脚本和 onclick 全拦了，红心点了没反应。
 * 换成「点了就跳一个链接」，这个链接由 Worker 接住、写进 KV、再回你一句"已收藏"。
 * 全程不需要 JS，也不需要你登录。
 *
 * 路由（{KEY} 是你在 Secret 里设的暗号，防止别人乱加）：
 *   GET /a/{KEY}/{owner}/{repo}?n=名字&o=一句话   加收藏，返回一个"已收藏"小页面
 *   GET /l/{KEY}                                网页看清单（手机上能直接开）
 *   GET /j/{KEY}                                返回 JSON（给电脑上的 fav.py 同步用）
 *   GET /d/{KEY}/{owner}/{repo}                 取消收藏
 *
 * 部署：详见 收藏夹-部署步骤.md
 */

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET,OPTIONS",
};

function page(title, body) {
  return new Response(`<!doctype html><html lang="zh-CN"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>${title}</title>
<style>
  body{margin:0;padding:26px 20px 40px;background:#fff7f7;
       font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Microsoft YaHei',sans-serif;
       color:#1b1b1f;line-height:1.75;-webkit-text-size-adjust:100%}
  .card{max-width:560px;margin:0 auto;background:#fff;border:1px solid #ffd9d9;border-radius:14px;
        padding:20px 18px;box-shadow:0 4px 18px rgba(229,72,77,.07)}
  h1{font-size:19px;margin:0 0 12px;color:#e5484d}
  .n{font-size:13px;color:#a56b6b}
  a.btn{display:inline-block;margin:16px 8px 0 0;padding:10px 18px;border-radius:10px;
        background:#e5484d;color:#fff;text-decoration:none;font-size:15px;font-weight:600}
  a.ghost{background:#fff;color:#e5484d;border:1.5px solid #e5484d}
  ul{padding-left:18px;margin:8px 0}
  li{margin:8px 0;font-size:15px}
  code{background:#f6f6f8;padding:1px 5px;border-radius:4px;font-size:13px}
  .del{font-size:12.5px;color:#c98a8a;text-decoration:none;margin-left:6px}
</style></head><body><div class="card">${body}</div></body></html>`,
  { headers: { "Content-Type": "text/html;charset=utf-8", "Cache-Control": "no-store", ...CORS } });
}

async function loadList(env) {
  try {
    return JSON.parse((await env.FAV_KV.get("list")) || "[]");
  } catch (e) {
    return [];
  }
}

async function saveList(env, list) {
  await env.FAV_KV.put("list", JSON.stringify(list.slice(-500)));
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (request.method === "OPTIONS") return new Response("ok", { headers: CORS });

    const parts = url.pathname.split("/").filter(Boolean);
    const action = (parts[0] || "").toLowerCase();
    const key = parts[1] || "";

    if (!key || key !== env.FAV_KEY) {
      return new Response("not found", { status: 404 });
    }

    const repo = parts.slice(2).map(decodeURIComponent).join("/");
    const list = await loadList(env);

    if (action === "a" || action === "add") {
      if (!repo.includes("/")) return new Response("bad repo", { status: 400 });
      const name = url.searchParams.get("n") || repo.split("/")[1];
      const one = (url.searchParams.get("o") || "").slice(0, 80);
      if (!list.some((x) => x.repo === repo)) {
        list.push({ repo, name, one, t: Date.now() });
        await saveList(env, list);
      }
      const n = list.filter((x) => x.repo).length;
      return page("已收藏", `
        <h1>❤ 已收藏</h1>
        <p><b>${name}</b><br><code>${repo}</code></p>
        <p class="n">这是你收藏的第 ${n} 个项目。收藏会在每一期之间累积。</p>
        <a class="btn" href="javascript:history.back()">← 返回刚才那篇</a>
        <a class="btn ghost" href="/l/${key}">看我的收藏清单</a>`);
    }

    if (action === "d" || action === "del") {
      const next = list.filter((x) => x.repo !== repo);
      await saveList(env, next);
      return page("已取消", `<h1>已取消收藏</h1><p><code>${repo}</code></p>
        <a class="btn" href="/l/${key}">回清单</a>`);
    }

    if (action === "j" || action === "json") {
      return new Response(JSON.stringify(list, null, 1), {
        headers: { "Content-Type": "application/json;charset=utf-8", "Cache-Control": "no-store", ...CORS },
      });
    }

    if (action === "l" || action === "list") {
      const items = list.filter((x) => x.repo);
      const rows = items.length
        ? items.map((x, i) => `<li><a href="https://github.com/${x.repo}" target="_blank"
             style="color:#1b1b1f;text-decoration:none"><b>${i + 1}. ${x.name || x.repo}</b></a><br>
             <span class="n">${x.repo}${x.one ? " — " + x.one : ""}</span>
             <a class="del" href="/d/${key}/${x.repo}">删除</a></li>`).join("")
        : `<li class="n">还没有收藏。在推送页面里点每张卡片右上角的爱心就行。</li>`;
      return page("我的收藏", `
        <h1>❤ 我的收藏 · ${items.length} 个</h1>
        <ul>${rows}</ul>
        <p class="n">这些收藏存在 Cloudflare，换手机、清缓存都不会丢。</p>`);
    }

    return new Response("not found", { status: 404 });
  },
};
