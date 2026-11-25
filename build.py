#!/usr/bin/env python3
"""Builds one demo page per prospects/<slug>.json into out/<slug>/index.html.

A file that fails validation gets an error page at out/<slug>/index.html that
lists every problem, so the agent that wrote it can fetch the URL, read what is
wrong and fix it. Other prospects are never affected.
"""
import glob, html, json, os, re, shutil, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "out")
TPL = open(os.path.join(ROOT, "template.html"), encoding="utf-8").read()

S = "str"
# field: (type, min_len, max_len) for strings; lists: (item_spec, min_items, max_items)
STR_FIELDS = {
    "business_name": (2, 60), "domain": (3, 80), "agent_name": (2, 24), "agent_role": (4, 40),
    "data_date": (6, 20),
    "hero_headline": (10, 70), "hero_emphasis": (3, 50), "hero_lead": (60, 320), "hero_cta": (8, 50),
    "pain_eyebrow": (4, 40), "pain_story": (80, 420), "pain_closer": (20, 140),
    "inbox_time": (3, 14), "inbox_label": (3, 30),
    "icp_headline": (10, 80), "icp_lead": (30, 240),
    "close_headline": (10, 90), "close_lead": (40, 260), "close_cta": (8, 50),
}
LIST_FIELDS = {
    "facts": ({"_str": (4, 60)}, 2, 4),
    "chips": ({"label": (4, 48), "question": (8, 240)}, 3, 5),
    "inbox": ({"channel": (2, 20), "time": (3, 14), "text": (4, 110)}, 2, 3),
    "icps": ({"who": (3, 40), "title": (8, 80), "pain": (30, 260), "fix": (30, 260), "question": (8, 240)}, 2, 3),
    "does": ({"title": (4, 40), "text": (20, 200)}, 3, 6),
    "faq": ({"q": (8, 100), "a": (20, 320)}, 3, 5),
}
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,48}[a-z0-9]$")
KEY_RE = re.compile(r"^hania_[A-Za-z0-9]{16,80}$")
HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")

def clean(s):
    # House style: no em or en dashes in client copy.
    return s.replace(" — ", ", ").replace("—", ", ").replace(" – ", ", ").replace("–", "-").strip()

def check_str(v, lo, hi, where, errs):
    if not isinstance(v, str) or not v.strip():
        errs.append(f"{where}: missing or not text"); return ""
    v = clean(v)
    if "<" in v or ">" in v:
        errs.append(f"{where}: plain text only, no HTML")
    if not lo <= len(v) <= hi:
        errs.append(f"{where}: {len(v)} characters, must be {lo} to {hi}")
    return v

def validate(cfg, slug):
    errs, out = [], {}
    if not isinstance(cfg, dict):
        return None, ["file is not a JSON object"]
    if cfg.get("slug") != slug:
        errs.append(f'slug: must be "{slug}" (same as the file name)')
    for k, (lo, hi) in STR_FIELDS.items():
        out[k] = check_str(cfg.get(k), lo, hi, k, errs)
    wk = cfg.get("widget_key", "")
    if not isinstance(wk, str) or not KEY_RE.match(wk):
        errs.append("widget_key: must be the hania_... key returned when the widget key was created")
    out["widget_key"] = wk if isinstance(wk, str) else ""
    acc = cfg.get("accent", "")
    if acc and not (isinstance(acc, str) and HEX_RE.match(acc)):
        errs.append("accent: optional, must look like #1f6feb")
    out["accent"] = acc if isinstance(acc, str) and HEX_RE.match(acc or "") else ""
    for k, (spec, lo, hi) in LIST_FIELDS.items():
        v = cfg.get(k)
        if not isinstance(v, list) or not lo <= len(v) <= hi:
            errs.append(f"{k}: must be a list of {lo} to {hi} items"); out[k] = []; continue
        items = []
        for i, it in enumerate(v):
            if "_str" in spec:
                items.append(check_str(it, *spec["_str"], f"{k}[{i}]", errs)); continue
            if not isinstance(it, dict):
                errs.append(f"{k}[{i}]: must be an object with {', '.join(spec)}"); continue
            items.append({f: check_str(it.get(f), lo2, hi2, f"{k}[{i}].{f}", errs) for f, (lo2, hi2) in spec.items()})
        out[k] = items
    unknown = set(cfg) - set(STR_FIELDS) - set(LIST_FIELDS) - {"slug", "widget_key", "accent", "brief"}
    if unknown:
        errs.append("unknown fields: " + ", ".join(sorted(unknown)))
    return out, errs

def e(s):
    return html.escape(s, quote=True)

def render(c):
    t = TPL
    blocks = {
        "FACTS": "".join(f"<span>{e(f)}</span>" for f in c["facts"]),
        "CHIPS": "".join(f'<button class="chip" data-q="{e(x["question"])}">{e(x["label"])}</button>' for x in c["chips"]),
        "INBOX": "".join(f'<div class="notif"><small><b>{e(x["channel"])}</b><span>{e(x["time"])}</span></small>{e(x["text"])}</div>' for x in c["inbox"]),
        "ICPS": "".join(
            f'<div class="icp reveal"><span class="who">{e(x["who"])}</span><h3>{e(x["title"])}</h3>'
            f'<p class="pain">{e(x["pain"])}</p><p class="fix"><b>What {e(c["agent_name"])} does</b>{e(x["fix"])}</p>'
            f'<button class="ask" data-q="{e(x["question"])}">Ask as this customer →</button></div>' for x in c["icps"]),
        "DOES": "".join(f'<div class="reveal"><span class="n">{i+1:02d}</span><h3>{e(x["title"])}</h3><p>{e(x["text"])}</p></div>' for i, x in enumerate(c["does"])),
        "FAQ": "".join(f'<details{" open" if i == 0 else ""}><summary>{e(x["q"])}</summary><p>{e(x["a"])}</p></details>' for i, x in enumerate(c["faq"])),
        "ACCENT_CSS": (f':root{{--accent:{c["accent"]};--accent-soft:color-mix(in srgb,{c["accent"]} 14%,#fff)}}'
                       f'@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--accent-soft:color-mix(in srgb,{c["accent"]} 22%,#000)}}}}'
                       if c["accent"] else ""),
        "initial": e(c["business_name"][:1].upper()),
    }
    for k, v in blocks.items():
        t = t.replace("{{" + k + "}}", v)
    for k in list(STR_FIELDS) + ["widget_key"]:
        t = t.replace("{{" + k + "}}", e(c[k]))
    left = re.findall(r"\{\{\w+\}\}", t)
    if left:
        raise RuntimeError(f"template placeholders not filled: {left}")
    return t

def error_page(slug, errs):
    items = "".join(f"<li>{e(x)}</li>" for x in errs)
    return (f'<!doctype html><meta charset="utf-8"><meta name="robots" content="noindex">'
            f'<title>BUILD ERROR {e(slug)}</title><body style="font:16px/1.5 system-ui;padding:32px;max-width:760px">'
            f'<h1>BUILD ERROR: prospects/{e(slug)}.json</h1><p>Fix these and commit the file again:</p><ul>{items}</ul></body>')

def main():
    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(OUT)
    ok = bad = 0
    for path in sorted(glob.glob(os.path.join(ROOT, "prospects", "*.json"))):
        slug = os.path.basename(path)[:-5]
        if not SLUG_RE.match(slug):
            print(f"skip {path}: bad file name"); continue
        os.makedirs(os.path.join(OUT, slug))
        try:
            cfg = json.load(open(path, encoding="utf-8"))
            c, errs = validate(cfg, slug)
        except json.JSONDecodeError as ex:
            c, errs = None, [f"not valid JSON: {ex}"]
        page = error_page(slug, errs) if errs else render(c)
        open(os.path.join(OUT, slug, "index.html"), "w", encoding="utf-8").write(page)
        print(("ERROR " if errs else "built ") + slug, *errs, sep="\n  ")
        bad += bool(errs); ok += not errs
    open(os.path.join(OUT, "index.html"), "w").write(
        '<!doctype html><meta charset="utf-8"><meta name="robots" content="noindex"><title>Private demos</title>'
        '<body style="font:16px system-ui;padding:40px">Private demos by Hania.ai.</body>')
    print(f"{ok} built, {bad} with errors")

if __name__ == "__main__":
    main()
