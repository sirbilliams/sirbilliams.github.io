#!/usr/bin/env python3
"""Generate the Thor Ports static site from GitHub releases. Stdlib only."""
import html, json, os, re, sys, urllib.request, urllib.error
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "site")
TOKEN = os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN") or os.environ.get("GITHUB_TOKEN")
e = html.escape


def get(url, raw=False):
    h = {"User-Agent": "thor-ports-build", "Accept": "application/vnd.github+json"}
    if TOKEN and "api.github.com" in url:
        h["Authorization"] = "Bearer " + TOKEN
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=20) as r:
            d = r.read().decode("utf-8", "replace")
            return d if raw else json.loads(d)
    except (urllib.error.URLError, OSError, ValueError) as ex:
        print("  warn: %s -> %s" % (url, ex), file=sys.stderr)
        return None


def raw_url(owner, repo, branch, path):
    path = path.strip().lstrip("./").lstrip("/")
    return "https://raw.githubusercontent.com/%s/%s/%s/%s" % (owner, repo, branch, path.replace(" ", "%20"))


def screenshots(md, owner, repo, branch, limit=3):
    urls = []
    cands = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', md) + re.findall(r'!\[[^\]]*\]\(([^)\s]+)', md)
    for u in cands:
        if "shields.io" in u or "badge" in u.lower() or u.lower().endswith(".svg"):
            continue
        if not re.search(r"\.(png|jpe?g|webp|gif)(\?|$)", u, re.I):
            continue
        if not u.startswith("http"):
            u = raw_url(owner, repo, branch, u)
        if u not in urls:
            urls.append(u)
        if len(urls) >= limit:
            break
    return urls


def inline(t):
    t = e(t)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2">\1</a>', t)
    t = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", t)
    return t


def install_steps(md):
    """Return HTML for the first install-ish README section, or ''."""
    secs = re.split(r"(?m)^(#{2,3})\s+(.+)$", md)
    for i in range(1, len(secs) - 2, 3):
        if re.search(r"install|getting started|setup|how to", secs[i + 1], re.I):
            body = secs[i + 2].split("\n")
            out, in_list, in_code = [], False, False
            for ln in body[:60]:
                if ln.strip().startswith("```"):
                    in_code = not in_code
                    out.append("<pre>" if in_code else "</pre>")
                    continue
                if in_code:
                    out.append(e(ln))
                    continue
                m = re.match(r"\s*(?:\d+\.|[-*])\s+(.*)", ln)
                if m:
                    if not in_list:
                        out.append("<ol>"); in_list = True
                    out.append("<li>%s</li>" % inline(m.group(1)))
                else:
                    if in_list:
                        out.append("</ol>"); in_list = False
                    if ln.strip() and not ln.strip().startswith(("|", "<", "![")):
                        out.append("<p>%s</p>" % inline(ln.strip()))
            if in_list: out.append("</ol>")
            if in_code: out.append("</pre>")
            return "<h3>%s</h3>\n%s" % (e(secs[i + 1].strip()), "\n".join(out))
    return ""


def fetch(owner, p):
    repo = p["repo"]
    print("fetching", repo)
    info = get("https://api.github.com/repos/%s/%s" % (owner, repo)) or {}
    branch = info.get("default_branch", "main")
    rel = get("https://api.github.com/repos/%s/%s/releases/latest" % (owner, repo))
    if not rel:  # no stable release: fall back to newest (pre-)release
        lst = get("https://api.github.com/repos/%s/%s/releases?per_page=1" % (owner, repo))
        rel = lst[0] if lst else None
    md = get("https://raw.githubusercontent.com/%s/%s/%s/README.md" % (owner, repo, branch), raw=True) or ""
    assets = (rel or {}).get("assets", [])
    apks = [a for a in assets if a["name"].lower().endswith(".apk")]
    fps = [a for a in assets if a["name"].lower().endswith(".flatpak")]
    title = (re.search(r"(?m)^#\s+(.+)$", md) or [None, repo])[1].strip()
    title = re.sub(r"[*_`]", "", title)
    return {
        "repo": repo, "owner": owner, "title": title,
        "tagline": p.get("tagline") or info.get("description") or "",
        "description": info.get("description") or "",
        "url": info.get("html_url") or "https://github.com/%s/%s" % (owner, repo),
        "release": ({"tag": rel.get("tag_name"), "date": (rel.get("published_at") or "")[:10],
                     "url": rel.get("html_url"), "pre": rel.get("prerelease")} if rel else None),
        "apks": apks, "flatpaks": fps,
        "shots": screenshots(md, owner, repo, branch),
        "install": install_steps(md),
        "flatpak": bool(fps) or bool(re.search(r"flatpak", md, re.I)),
    }


def size(a):
    return "%.0f MB" % (a.get("size", 0) / 1048576) if a.get("size") else ""


def badges(p):
    b = ['<span class="b">Android</span>', '<span class="b thor">Thor</span>']
    if p["flatpak"]:
        b.append('<span class="b">Flatpak</span>')
    return '<div class="badges">%s</div>' % "".join(b)


def buttons(p):
    out = []
    for a in p["apks"] + p["flatpaks"]:
        kind = "APK" if a["name"].lower().endswith(".apk") else "Flatpak"
        out.append('<a class="btn" href="%s" download>%s <small>%s %s</small></a>' % (
            e(a["browser_download_url"]), kind, e(a["name"]) if len(p["apks"] + p["flatpaks"]) > 2 else "", size(a)))
    if not out:
        out.append('<a class="btn ghost" href="%s">No release yet: see the repo</a>' % e(p["url"]))
    return '<div class="btns">%s</div>' % "".join(out)


def rel_line(p):
    r = p["release"]
    if not r:
        return '<p class="rel">No published release</p>'
    return '<p class="rel"><a href="%s">%s</a> &middot; %s%s</p>' % (
        e(r["url"] or p["url"]), e(r["tag"] or "release"), e(r["date"]), " &middot; pre-release" if r["pre"] else "")


def screen(p, n=2, cls=""):
    if not p["shots"]:
        return '<div class="device %s"><div class="scr empty">no screenshot</div><div class="scr empty"></div></div>' % cls
    shots = p["shots"][:n]
    return '<div class="device %s">%s</div>' % (cls, "".join(
        '<div class="scr"><img loading="lazy" src="%s" alt="%s screenshot"></div>' % (e(s), e(p["title"])) for s in shots))


NOTE = '<p class="note">You need your own copy of the game. These apps contain no game data.</p>'

CSS = """
:root{--bg:#f2efe8;--ink:#1c1b22;--mute:#5d5b68;--card:#fff;--shell:#2b2a36;--glass:#0d0e14;--acc:#e8541e;--acc2:#1f8a8a;--line:#d9d4c7}
@media(prefers-color-scheme:dark){:root{--bg:#0f0f15;--ink:#ece9f2;--mute:#9b98a8;--card:#191922;--shell:#3a3946;--glass:#05060a;--acc:#ff7a45;--acc2:#4fd1c5;--line:#2a2a36}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 ui-rounded,"Trebuchet MS",system-ui,sans-serif;
background-image:radial-gradient(var(--line) 1px,transparent 1px);background-size:18px 18px}
.wrap{max-width:1080px;margin:0 auto;padding:0 16px 60px}
header{padding:36px 0 18px}
h1{font:800 clamp(2rem,6vw,3.4rem)/1 "Arial Black",Impact,sans-serif;letter-spacing:-.03em;margin:0;text-transform:uppercase}
h1 span{color:var(--acc)}
.sub{color:var(--mute);max-width:56ch;margin:.6rem 0 0}
a{color:var(--acc2)}
.grid{display:grid;gap:22px;grid-template-columns:repeat(auto-fill,minmax(min(100%,460px),1fr))}
.card{background:var(--card);border:2px solid var(--shell);border-radius:22px;padding:16px;box-shadow:6px 6px 0 var(--shell);display:flex;flex-direction:column;gap:10px}
.device{background:var(--shell);border-radius:16px;padding:8px;display:grid;gap:6px;grid-template-rows:1fr 1fr;position:relative}
.device.row{grid-template-rows:none;grid-template-columns:1fr 1fr}
.device::after{content:"";position:absolute;left:50%;top:50%;width:26px;height:4px;margin:-2px 0 0 -13px;background:var(--acc);border-radius:2px}
.device.row::after{width:4px;height:26px;margin:-13px 0 0 -2px}
.scr{background:var(--glass);border-radius:8px;aspect-ratio:16/9;overflow:hidden;display:grid;place-items:center;color:var(--mute);font-size:.8rem}
.scr img{width:100%;height:100%;object-fit:cover;display:block}
.card .device{grid-template-rows:none;grid-template-columns:1fr 1fr}
.card .device::after{width:4px;height:26px;margin:-13px 0 0 -2px}
h2{margin:.2rem 0 0;font-size:1.25rem}
h2 a{color:var(--ink);text-decoration:none}
.badges{display:flex;gap:6px;flex-wrap:wrap}
.b{font:700 .72rem/1 ui-monospace,monospace;text-transform:uppercase;letter-spacing:.06em;border:1.5px solid var(--shell);border-radius:6px;padding:4px 7px}
.b.thor{background:var(--acc);color:#fff;border-color:var(--acc)}
.tag{margin:0;color:var(--mute)}
.btns{display:flex;gap:8px;flex-wrap:wrap}
.btn{display:inline-block;background:var(--ink);color:var(--bg);text-decoration:none;font-weight:700;border-radius:10px;padding:10px 14px;min-height:44px}
.btn small{font-weight:400;opacity:.7;margin-left:4px}
.btn.ghost{background:transparent;color:var(--ink);border:2px dashed var(--mute)}
.note{font-size:.85rem;color:var(--mute);margin:0;border-left:3px solid var(--acc);padding-left:8px}
.rel{margin:0;font:.8rem ui-monospace,monospace;color:var(--mute)}
.links{display:flex;gap:14px;font-size:.9rem}
.detail{background:var(--card);border:2px solid var(--shell);border-radius:22px;padding:18px;box-shadow:6px 6px 0 var(--shell);margin-top:18px}
.detail pre{background:var(--glass);color:#d7f5e8;padding:12px;border-radius:8px;overflow:auto}
.detail code{font-family:ui-monospace,monospace;background:var(--line);padding:1px 4px;border-radius:4px;word-break:break-word}
.detail pre code{background:none}
.shots{display:grid;gap:14px;margin:14px 0}
footer{color:var(--mute);font-size:.8rem;margin-top:32px}
@media(max-width:560px){.card .device{grid-template-columns:none;grid-template-rows:1fr 1fr}.card .device::after{width:26px;height:4px;margin:-2px 0 0 -13px}}
"""


def page(title, body, back=False):
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1"><title>%s</title>'
            '<style>%s</style></head><body><div class="wrap">%s'
            '<footer>Built %s from GitHub releases. Unofficial fan projects, not affiliated with any rights holder.</footer></div></body></html>'
            % (e(title), CSS, body, datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")))


def card(p):
    return ('<article class="card">%s<h2><a href="%s.html">%s</a></h2>%s<p class="tag">%s</p>%s%s%s%s'
            '<div class="links"><a href="%s.html">Details &amp; install</a><a href="%s">GitHub</a></div></article>') % (
        screen(p), e(p["repo"]), e(p["title"]), badges(p), e(p["tagline"]), rel_line(p), buttons(p), NOTE, "",
        e(p["repo"]), e(p["url"]))


def detail(p):
    inst = p["install"] or '<p>See the <a href="%s#readme">README on GitHub</a> for install steps.</p>' % e(p["url"])
    shots = "".join('<div class="device row"><div class="scr"><img loading="lazy" src="%s" alt=""></div></div>' % e(s) for s in p["shots"])
    body = ('<header><a href="index.html">&larr; All ports</a><h1 style="font-size:clamp(1.6rem,5vw,2.6rem);margin-top:12px">%s</h1>'
            '<p class="sub">%s</p>%s</header>%s%s%s%s<div class="detail">%s</div>'
            '<p><a href="%s">Source, README and issues on GitHub</a></p>') % (
        e(p["title"]), e(p["tagline"]), badges(p), rel_line(p), buttons(p), NOTE,
        '<div class="shots">%s</div>' % shots if shots else "", inst, e(p["url"]))
    return page(p["title"] + " | Thor Ports", body)


def main():
    cfg = json.load(open(os.path.join(ROOT, "ports.json")))
    ports = [fetch(cfg["owner"], p) for p in cfg["ports"]]
    os.makedirs(OUT, exist_ok=True)
    head = ('<header><h1>Thor <span>Ports</span></h1><p class="sub">Native Android ports of classic PC games, built for the '
            'dual-screen AYN Thor. Free, open source, bring your own copy of the game.</p></header>')
    open(os.path.join(OUT, "index.html"), "w").write(page("Thor Ports", head + '<main class="grid">%s</main>' % "".join(card(p) for p in ports)))
    for p in ports:
        open(os.path.join(OUT, p["repo"] + ".html"), "w").write(detail(p))
    for p in ports:
        print("%-32s release=%-10s apk=%d flatpak=%d shots=%d install=%s" % (
            p["repo"], (p["release"] or {}).get("tag"), len(p["apks"]), len(p["flatpaks"]), len(p["shots"]), bool(p["install"])))
    print("wrote", len(ports) + 1, "pages")


if __name__ == "__main__":
    main()
