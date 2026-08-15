"""Build a zero-dependency immersive HTML gallery for a photo-card session."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path

from build_spatial_exhibition import build_spatial


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def extract_visual_motifs(analysis: str) -> tuple[list[str], list[str]]:
    facts = []
    for line in analysis.splitlines():
        if line.startswith("|") and "---" not in line and "观察事实" not in line:
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if cells and len(cells[0]) > 4:
                facts.append(cells[0].rstrip("。"))
    keyword_names = (
        ("城市", "城市"), ("建筑群", "城市"), ("高楼", "楼影"),
        ("天际线", "天际线"), ("天空", "天空"), ("树枝", "枝影"), ("树干", "枝影"),
        ("太阳", "日光"), ("阳光", "日光"), ("飞机", "远行"),
        ("云", "云层"), ("人物", "观察者"), ("成年人", "观察者"),
        ("森林", "林间"), ("林间", "林间"), ("石头", "石上图案"),
        ("路径", "路径"), ("水", "水面"), ("建筑", "建筑"),
        ("花", "花影"), ("山", "远山"), ("海", "海面"),
    )
    motifs = []
    for keyword, name in keyword_names:
        if keyword in analysis and name not in motifs:
            motifs.append(name)
    while len(motifs) < 4:
        motifs.append(("光线", "轮廓", "留白", "片刻")[len(motifs)])
    return motifs[:6], facts[:8]


def curate_record(item: dict, index: int, analysis: str) -> dict:
    motifs, facts = extract_visual_motifs(analysis)
    a, b, c, d = motifs[:4]
    title_templates = (
        f"{a}的轻线", f"{a}与{b}之间", f"为{a}留白", f"{c}的记忆层",
        f"两种注视", f"{b}留下的纹理", f"观看的坐标", f"柔光档案",
        f"{a}缓慢经过", f"{c}手记", f"{b}的形态研究", f"被保存的{c}",
        f"观察练习", f"日光颗粒", f"一段可读的风景", f"色彩与方向",
        f"片刻档案", f"轮廓复写", f"{d}一隅", f"移动的凝视",
        f"纸上的{a}", f"观看手记", f"一帧远意", f"{c}静观",
    )
    title = title_templates[index % len(title_templates)]
    style_name = item["label"].split("/")[-1].strip()
    fact = facts[index % len(facts)] if facts else f"画面以{a}、{b}与{c}构成主要视觉关系"
    description = (
        f"以{fact}为视觉依据，保留原图的主体关系与真实光线。"
        f"通过克制的{style_name}语言，重新组织{a}、{b}与留白之间的节奏。"
    )
    item["curatorial_title"] = title
    item["curatorial_description"] = description
    item["style_note"] = style_name
    return item


def build(delivery: Path) -> tuple[Path, Path]:
    delivery = delivery.resolve()
    preview_dir = delivery / "previews"
    session = load_json(delivery / "session.json")
    catalog_path = delivery / "catalog.snapshot.json"
    catalog = load_json(catalog_path)
    selection = load_json(delivery / "selection-map.json")
    analysis_path = delivery / "analysis.md"
    analysis = analysis_path.read_text(encoding="utf-8") if analysis_path.is_file() else ""
    catalog_items = {
        item["id"]: item
        for item in catalog["native_presets"] + catalog["reference_result_presets"]
    }
    records: list[dict] = []
    for mapped in selection["presets"]:
        preset_id = mapped["id"]
        item = catalog_items[preset_id]
        state = session["preview_status"][preset_id]
        image_path = preview_dir / f"{preset_id}.png"
        if not image_path.is_file():
            raise SystemExit(f"missing preview image: {image_path}")
        records.append(
            curate_record({
                "number": mapped["number"],
                "number_text": f"{mapped['number']:02d}",
                "id": preset_id,
                "label": item["label"],
                "kind": item["kind"],
                "group": "原生视觉语言"
                if item["kind"] == "native"
                else "参考项目结果格式",
                "source": item.get("source", "LaplaceLajiang-photo-card"),
                "status": state["status"],
                "reason": state.get("reason", ""),
                "image": f"{preset_id}.png",
                "sha256": sha256(image_path),
            }, len(records), analysis)
        )

    complete = [record for record in records if record["status"] == "complete"]
    hero_records = (complete or records)[:3]
    hero_layer_parts = []
    for index, item in enumerate(hero_records):
        priority = ' fetchpriority="high"' if index == 0 else ""
        hero_layer_parts.append(
            f'<img class="hero-card hero-card--{index + 1}" '
            f'src="{esc(item["image"])}" alt="" aria-hidden="true"{priority}>'
        )
    hero_layers = "\n".join(hero_layer_parts)
    index_cards = "\n".join(
        f'<a class="index-card" href="#style-{item["number_text"]}" '
        f'data-filter-kind="{esc(item["kind"])}">'
        f'<span>{item["number_text"]}</span><strong data-fit-title>{esc(item["curatorial_title"])}</strong>'
        f'<small>风格 · {esc(item["style_note"])}</small></a>'
        for item in records
    )
    rooms = []
    for index, item in enumerate(records):
        eager = ' loading="eager" fetchpriority="high"' if index < 2 else ' loading="lazy"'
        state_note = (
            "可选择"
            if item["status"] == "complete"
            else f"预览不可用：{item['reason'] or '生成失败'}"
        )
        disabled = "" if item["status"] == "complete" else " disabled"
        rooms.append(
            f'''<section class="room room--{index % 3}" id="style-{item["number_text"]}"
              data-room data-number="{item["number_text"]}" data-kind="{esc(item["kind"])}">
  <div class="room-number" aria-hidden="true">{item["number_text"]}</div>
  <div class="room-copy">
    <p class="eyebrow">作品 {item["number_text"]}/{len(records):02d}</p>
    <h2 data-fit-title>{esc(item["curatorial_title"])}</h2>
    <p class="source">{esc(item["curatorial_description"])}</p>
    <p class="state">风格 · {esc(item["style_note"])}</p>
    <p class="state state--{esc(item["status"])}">{esc(state_note)}</p>
    <button class="select-button" type="button" data-select="#{item["number_text"]}" aria-pressed="false"{disabled}>
      加入收藏 #{item["number_text"]}
    </button>
  </div>
  <button class="artwork" type="button" data-open="{esc(item["id"])}"
          aria-label="放大查看 #{item["number_text"]} {esc(item["curatorial_title"])}">
    <img src="{esc(item["image"])}" alt="#{item["number_text"]} {esc(item["curatorial_title"])} 缩略图" draggable="false"{eager}>
  </button>
  <a class="next-room" href="#{'exit' if index == len(records) - 1 else 'style-' + records[index + 1]['number_text']}">
    {"结束参观" if index == len(records) - 1 else "下一展厅"} <span aria-hidden="true">↓</span>
  </a>
</section>'''
        )

    manifest = {
        "schema_version": 1,
        "gallery_contract": "immersive-html+static-png",
        "catalog_sha256": sha256(catalog_path),
        "offline": True,
        "external_runtime_dependencies": [],
        "interaction": {
            "keyboard": ["ArrowDown", "ArrowRight", "ArrowUp", "ArrowLeft", "Escape"],
            "reduced_motion": True,
            "static_fallback": "style-gallery.png",
        },
        "design_inspiration": [
            {
                "name": "Kage",
                "url": "https://mengto.github.io/kage/",
                "borrowed_principles": [
                    "full-screen entrance",
                    "chaptered scroll rhythm",
                    "large numbering",
                    "dark focus environment",
                    "persistent progress",
                ],
                "copied_assets_or_code": False,
            },
            {
                "name": "MengTo Skills",
                "url": "https://github.com/MengTo/skills",
                "license": "MIT",
                "borrowed_principles": [
                    "portable demo",
                    "explicit defaults and constraints",
                    "work-first editorial hierarchy",
                    "restrained 500-760ms project transitions",
                    "stable hero and readable static metadata",
                    "animation performance and reduced-motion safeguards",
                ],
                "skills_applied": [
                    "build-awwwards-quality-sites",
                    "threejs",
                    "editorial-portfolio-chapters",
                    "optimize-web-animations",
                ],
                "copied_assets_or_code": False,
            },
        ],
        "items": records,
    }
    manifest_path = preview_dir / "gallery-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    data_json = json.dumps(records, ensure_ascii=False).replace("<", "\\u003c")

    document = DOCUMENT.replace("__HERO_LAYERS__", hero_layers)
    document = document.replace("__INDEX_CARDS__", index_cards)
    document = document.replace("__ROOMS__", "\n".join(rooms))
    document = document.replace("__TOTAL__", str(len(records)))
    document = document.replace("__TOTAL_PADDED__", f"{len(records):02d}")
    document = document.replace("__GALLERY_DATA__", data_json)
    accessible = preview_dir / "style-gallery-accessible.html"
    accessible.write_text(document, encoding="utf-8")
    output = build_spatial(delivery)
    return output, manifest_path


DOCUMENT = r'''<!doctype html>
<html lang="zh-CN" data-gallery-version="1">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
  <meta name="color-scheme" content="dark">
  <title>Style Atlas · LaplaceLajiang Photo Card</title>
  <style>
    :root{--ink:#3b2b21;--paper:#fff9ed;--muted:#806d5d;--line:rgba(99,66,43,.18);--accent:#c96f4e;--progress:0%;font-family:Inter,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;color:var(--ink);background:#ead6bf}
    *{box-sizing:border-box}html{scroll-behavior:smooth;scroll-snap-type:y proximity;background:var(--ink)}body{margin:0;background:var(--ink);color:var(--paper);overflow-x:hidden}body::before{content:"";position:fixed;inset:0;pointer-events:none;z-index:50;opacity:.12;background-image:repeating-radial-gradient(circle at 20% 30%,transparent 0 1px,rgba(255,255,255,.12) 1px 2px);background-size:5px 5px;mix-blend-mode:soft-light}.skip-link{position:fixed;left:1rem;top:-4rem;z-index:100;padding:.75rem 1rem;background:var(--paper);color:var(--ink)}.skip-link:focus{top:1rem}.topbar{position:fixed;z-index:40;inset:0 0 auto;display:grid;grid-template-columns:1fr auto 1fr;align-items:center;padding:1rem 1.5rem;border-bottom:1px solid transparent;transition:background .3s,border .3s}.topbar.is-scrolled{background:rgba(8,10,9,.84);backdrop-filter:blur(16px);border-color:var(--line)}.brand,.topbar a{color:inherit;text-decoration:none}.brand{font-weight:800;letter-spacing:-.04em}.brand small{display:block;font-size:.54rem;letter-spacing:.2em;color:var(--muted)}.chapter-nav{display:flex;gap:1.25rem;font-size:.68rem;letter-spacing:.16em;text-transform:uppercase}.chapter-nav a:hover,.chapter-nav a:focus-visible{color:var(--accent)}.counter{justify-self:end;font-variant-numeric:tabular-nums;font-size:.75rem}.progress{position:fixed;z-index:45;right:1.1rem;top:20%;height:60%;width:1px;background:var(--line)}.progress::after{content:"";display:block;width:3px;height:var(--progress);margin-left:-1px;background:var(--accent);transition:height .15s linear}.hero{position:relative;min-height:100svh;display:grid;align-content:end;padding:7rem clamp(1.25rem,5vw,5rem) 4rem;overflow:hidden;scroll-snap-align:start}.hero::after{content:"";position:absolute;inset:0;background:linear-gradient(90deg,rgba(8,10,9,.95),rgba(8,10,9,.18) 58%,rgba(8,10,9,.75)),linear-gradient(0deg,var(--ink),transparent 45%);z-index:-1}.hero-stage{position:absolute;inset:0;z-index:-2;filter:saturate(.76) contrast(1.08)}.hero-card{position:absolute;width:min(48vw,650px);height:78svh;object-fit:cover;box-shadow:0 2rem 6rem #000;transition:transform .8s cubic-bezier(.2,.75,.25,1)}.hero-card--1{right:8vw;top:10svh;transform:rotate(3deg)}.hero-card--2{right:-12vw;top:18svh;transform:rotate(-5deg) scale(.84);opacity:.56}.hero-card--3{right:35vw;top:-28svh;transform:rotate(8deg) scale(.66);opacity:.32}.hero-kicker,.eyebrow{margin:0 0 1rem;font-size:.66rem;letter-spacing:.24em;text-transform:uppercase;color:var(--accent)}.hero h1{max-width:8ch;margin:0;font-size:clamp(4.5rem,14vw,13rem);line-height:.72;letter-spacing:-.09em;text-transform:uppercase}.hero h1 span{display:block;margin-left:.72em;color:transparent;-webkit-text-stroke:1px var(--paper)}.hero-meta{display:flex;align-items:end;gap:3rem;margin-top:2.5rem}.hero-meta p{max-width:32rem;margin:0;color:#c0c1bb;line-height:1.7}.enter{color:inherit;text-decoration:none;border-bottom:1px solid var(--paper);padding:.5rem 0;white-space:nowrap}.atlas-index{min-height:100svh;padding:8rem clamp(1.25rem,6vw,7rem);border-top:1px solid var(--line)}.section-head{display:flex;justify-content:space-between;align-items:end;gap:2rem;margin-bottom:3rem}.section-head h2{margin:0;font-size:clamp(2.5rem,7vw,7rem);line-height:.9;letter-spacing:-.07em}.filters{display:flex;gap:.5rem;flex-wrap:wrap}.filter{border:1px solid var(--line);background:transparent;color:inherit;border-radius:999px;padding:.65rem 1rem;cursor:pointer}.filter[aria-pressed=true],.filter:hover{background:var(--paper);color:var(--ink)}.index-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));border-top:1px solid var(--line);border-left:1px solid var(--line)}.index-card{min-height:9rem;padding:1rem;display:flex;flex-direction:column;color:inherit;text-decoration:none;border-right:1px solid var(--line);border-bottom:1px solid var(--line);transition:background .25s,color .25s,transform .25s}.index-card:hover,.index-card:focus-visible{background:var(--paper);color:var(--ink);transform:translateY(-3px)}.index-card[hidden]{display:none}.index-card span{font-size:.72rem;color:var(--accent)}.index-card strong{margin:auto 0 .6rem;font-size:clamp(1rem,1.5vw,1.35rem);line-height:1.1}.index-card small{opacity:.58}.room{position:relative;min-height:100svh;padding:7rem clamp(1.25rem,6vw,7rem) 4rem;display:grid;grid-template-columns:minmax(15rem,.75fr) minmax(20rem,1.45fr);grid-template-rows:1fr auto;align-items:center;gap:2rem 6vw;border-top:1px solid var(--line);overflow:hidden;scroll-snap-align:start}.room-number{position:absolute;left:-.03em;top:50%;transform:translateY(-54%);font-size:clamp(14rem,38vw,42rem);line-height:.7;font-weight:900;letter-spacing:-.12em;color:rgba(233,231,223,.025);pointer-events:none}.room-copy{position:relative;z-index:2;max-width:33rem}.room-copy h2{margin:0 0 1rem;font-size:clamp(2.7rem,6vw,7rem);line-height:.86;letter-spacing:-.07em}.source,.state{color:var(--muted);line-height:1.55}.state--failed{color:#e59a8a}.select-button{margin-top:1.5rem;border:1px solid var(--paper);background:transparent;color:inherit;padding:.85rem 1.25rem;font:inherit;cursor:pointer;transition:.2s}.select-button:hover,.select-button:focus-visible{background:var(--accent);border-color:var(--accent);color:#090909}.select-button:disabled{opacity:.35;cursor:not-allowed}.artwork{position:relative;z-index:2;justify-self:center;border:0;padding:0;background:transparent;cursor:zoom-in;filter:drop-shadow(0 2rem 4rem #000);transform:translateY(var(--drift,0)) rotate(1deg);transition:filter .35s}.artwork img{display:block;width:min(48vw,640px);max-height:76svh;object-fit:contain;background:#111}.room--1 .artwork{transform:translateY(var(--drift,0)) rotate(-1.5deg)}.room--2 .artwork{transform:translateY(var(--drift,0)) rotate(.4deg)}.artwork:hover{filter:drop-shadow(0 2.5rem 5rem #000) brightness(1.05)}.next-room{grid-column:1/-1;justify-self:end;color:var(--muted);text-decoration:none;font-size:.7rem;letter-spacing:.18em;text-transform:uppercase}.exit{min-height:72svh;display:grid;place-items:center;text-align:center;padding:6rem 1.5rem;border-top:1px solid var(--line)}.exit h2{font-size:clamp(3rem,10vw,9rem);letter-spacing:-.08em;margin:.25rem}.exit p{color:var(--muted)}.exit a{color:var(--paper)}dialog{width:min(92vw,1100px);height:min(90svh,900px);border:0;padding:0;background:#080a09;color:var(--paper);box-shadow:0 2rem 8rem #000}dialog::backdrop{background:rgba(0,0,0,.82);backdrop-filter:blur(8px)}.viewer-inner{height:100%;display:grid;grid-template-rows:auto 1fr auto;padding:1rem}.viewer-close{justify-self:end;border:0;background:transparent;color:inherit;font-size:1.6rem;cursor:pointer}.viewer-image{width:100%;height:100%;object-fit:contain;min-height:0}.viewer-caption{padding:.75rem;text-align:center;color:var(--muted)}.selection-toast{position:fixed;z-index:80;left:50%;bottom:1.25rem;transform:translate(-50%,140%);display:flex;align-items:center;gap:1rem;padding:.8rem 1rem;background:var(--paper);color:var(--ink);box-shadow:0 1rem 4rem #000;transition:transform .35s}.selection-toast.is-visible{transform:translate(-50%,0)}.selection-toast button{border:0;background:var(--ink);color:var(--paper);padding:.55rem .8rem;cursor:pointer}:focus-visible{outline:2px solid var(--accent);outline-offset:4px}
    .hero{isolation:isolate}.ticket{position:absolute;right:4vw;bottom:3rem;z-index:2;width:min(18rem,35vw);padding:1rem;background:#e8e3d6;color:#171713;transform:rotate(-3deg);box-shadow:0 1rem 3rem #000}.ticket::before{content:"ADMIT ONE";display:block;border-bottom:1px dashed #777;padding-bottom:.6rem;margin-bottom:.6rem;font-size:.62rem;letter-spacing:.25em}.ticket strong{display:block;font-size:1.5rem}.ticket small{display:block;margin-top:.5rem;color:#68645b}.room{isolation:isolate;perspective:1200px;background:linear-gradient(115deg,#191a18 0 16%,#292925 16% 78%,#151614 78%)}.room::before{content:"";position:absolute;z-index:-2;left:0;right:0;bottom:0;height:28%;background:repeating-linear-gradient(100deg,transparent 0 11vw,rgba(255,255,255,.035) 11vw calc(11vw + 1px)),linear-gradient(#171815,#070807);clip-path:polygon(8% 0,92% 0,100% 100%,0 100%)}.room::after{content:"";position:absolute;z-index:-2;inset:0 0 auto;height:18%;background:linear-gradient(#080908,#1c1d1a);clip-path:polygon(0 0,100% 0,91% 100%,9% 100%)}.artwork{border:clamp(.65rem,1.3vw,1.2rem) solid #171511;outline:1px solid #786e5e;padding:clamp(.5rem,1vw,.9rem);background:#2d2821;box-shadow:0 2rem 4rem #000,0 .5rem 1rem #000,inset 0 0 0 2px #0e0d0b;filter:none;transform:translateY(var(--drift,0)) rotateY(-2deg)}.artwork img{width:min(45vw,600px);max-height:68svh}.artwork::after{content:"";position:absolute;inset:0;pointer-events:none;box-shadow:inset 0 0 3rem rgba(0,0,0,.42)}.room--1 .artwork,.room--2 .artwork{transform:translateY(var(--drift,0)) rotateY(2deg)}.select-button[aria-pressed=true]{background:var(--accent);border-color:var(--accent);color:#090909}.collection-tray{position:fixed;z-index:70;right:2rem;bottom:2rem;display:flex;gap:.8rem;align-items:center;padding:.65rem .8rem;background:rgba(8,10,9,.88);border:1px solid var(--line);backdrop-filter:blur(14px);transform:translateY(8rem);transition:transform .3s}.collection-tray.is-visible{transform:none}.collection-tray strong{color:var(--accent)}.collection-tray button{border:0;background:var(--paper);color:var(--ink);padding:.65rem .8rem;cursor:pointer}
    [data-fit-title]{white-space:nowrap!important;max-width:100%;line-height:1.06}.index-card strong{overflow:hidden;text-overflow:clip}.room-copy{min-width:0}.room-copy h2{width:100%}
    @media(max-width:850px){.topbar{grid-template-columns:1fr auto}.chapter-nav{display:none}.hero{padding-bottom:2.5rem}.hero-card{width:75vw;height:68svh}.hero-card--1{right:-8vw}.hero-card--2{right:-36vw}.hero-card--3{display:none}.hero h1{font-size:clamp(4rem,23vw,8rem)}.hero-meta{display:block}.hero-meta p{margin-bottom:1.5rem}.ticket{display:none}.index-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.room{grid-template-columns:1fr;grid-template-rows:auto 1fr auto;padding-top:6.5rem;gap:1.5rem;background:#20211f}.room-copy h2{font-size:clamp(2.5rem,13vw,5.5rem)}.artwork{order:-1}.artwork img{width:min(78vw,580px);max-height:50svh}.next-room{grid-column:1}.progress{right:.55rem}.selection-toast{width:calc(100% - 2rem);justify-content:space-between}.collection-tray{left:1rem;right:1rem;bottom:1rem;justify-content:space-between}}
    @media(prefers-reduced-motion:reduce){html{scroll-behavior:auto;scroll-snap-type:none}*,*::before,*::after{animation:none!important;transition:none!important}.artwork,.room--1 .artwork,.room--2 .artwork{transform:none!important}}
  </style>
</head>
<body>
  <a class="skip-link" href="#atlas">跳到风格索引</a>
  <header class="topbar" aria-label="展览导航">
    <a class="brand" href="#entrance">STYLE ATLAS<small>LAPLACELAJIANG PHOTO CARD</small></a>
    <nav class="chapter-nav"><a href="#atlas">索引</a><a href="#style-01">展厅</a><a href="#exit">选择</a></nav>
    <div class="counter" aria-live="polite"><span id="current">00</span> / __TOTAL_PADDED__</div>
  </header>
  <div class="progress" aria-hidden="true"></div>
  <main>
    <section class="hero" id="entrance">
      <div class="hero-stage" aria-hidden="true">__HERO_LAYERS__</div>
      <p class="hero-kicker">IMMERSIVE PREVIEW EXHIBITION · __TOTAL__ DIRECTIONS</p>
      <h1>Style<span>Atlas</span></h1>
      <div class="hero-meta"><p>沿展览路径比较全部预设。每一间展厅都保留同一输入证据，只改变视觉语言与结果格式。</p><a class="enter" href="#atlas">进入展览 ↓</a></div>
      <div class="ticket" aria-hidden="true"><strong>STYLE ATLAS</strong><small>__TOTAL_PADDED__ ROOMS · TAKE HOME UP TO 6</small></div>
    </section>
    <section class="atlas-index" id="atlas">
      <div class="section-head"><div><p class="eyebrow">Exhibition index</p><h2>全部方向</h2></div><div class="filters" role="group" aria-label="筛选风格"><button class="filter" type="button" data-filter="all" aria-pressed="true">全部</button><button class="filter" type="button" data-filter="native" aria-pressed="false">原生</button><button class="filter" type="button" data-filter="reference-result" aria-pressed="false">参考结果</button></div></div>
      <div class="index-grid">__INDEX_CARDS__</div>
      <noscript><p>浏览器已关闭 JavaScript；仍可继续滚动参观，或打开 <a href="style-gallery.png">静态总览图</a>。</p></noscript>
    </section>
    __ROOMS__
    <section class="exit" id="exit"><div><p class="eyebrow">Museum shop · End of exhibition</p><h2>把喜欢的带走</h2><p>可收藏 1–6 幅作品。确认后复制收藏单并回复；接下来会逐幅进行高清制作、装裱、打包，并告知保存路径。</p><button class="select-button" type="button" id="finish-visit">完成参观并复制收藏单</button><p><a href="style-gallery.png">打开静态总览图</a> · <a href="#atlas">返回索引</a></p></div></section>
  </main>
  <dialog id="viewer" aria-labelledby="viewer-caption"><div class="viewer-inner"><button class="viewer-close" type="button" aria-label="关闭">×</button><img class="viewer-image" alt=""><p class="viewer-caption" id="viewer-caption"></p></div></dialog>
  <div class="selection-toast" role="status" aria-live="polite"><span id="selection-message"></span><button type="button" id="copy-selection">复制编号</button></div>
  <div class="collection-tray" aria-live="polite"><span>收藏袋 <strong id="collection-count">0</strong>/6</span><button type="button" id="review-collection">查看并带走</button></div>
  <script id="gallery-data" type="application/json">__GALLERY_DATA__</script>
  <script>
    (function(){
      'use strict';
      var data=JSON.parse(document.getElementById('gallery-data').textContent);
      var byId={}; data.forEach(function(item){byId[item.id]=item});
      var rooms=Array.prototype.slice.call(document.querySelectorAll('[data-room]'));
      var current=document.getElementById('current');
      var topbar=document.querySelector('.topbar');
      var toast=document.querySelector('.selection-toast');
      var message=document.getElementById('selection-message');
      var selected=[];
      var reduced=window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      function fitTitle(node){if(!node)return;node.style.fontSize='';var size=parseFloat(getComputedStyle(node).fontSize),minimum=node.closest('.index-card')?11:18,guard=80;while(node.scrollWidth>node.clientWidth&&size>minimum&&guard--){size-=.5;node.style.fontSize=size+'px'}}function fitTitles(){document.querySelectorAll('[data-fit-title]').forEach(fitTitle)}
      function updateProgress(){var max=document.documentElement.scrollHeight-innerHeight;var value=max>0?scrollY/max*100:0;document.documentElement.style.setProperty('--progress',value+'%');topbar.classList.toggle('is-scrolled',scrollY>24)}
      var observer=new IntersectionObserver(function(entries){entries.forEach(function(entry){if(entry.isIntersecting){current.textContent=entry.target.dataset.number;entry.target.classList.add('is-active')}})},{threshold:.54});rooms.forEach(function(room){observer.observe(room)});
      document.querySelectorAll('.filter').forEach(function(button){button.addEventListener('click',function(){var value=button.dataset.filter;document.querySelectorAll('.filter').forEach(function(item){item.setAttribute('aria-pressed',String(item===button))});document.querySelectorAll('.index-card').forEach(function(card){card.hidden=value!=='all'&&card.dataset.filterKind!==value})})});
      var tray=document.querySelector('.collection-tray');var count=document.getElementById('collection-count');function updateCollection(){count.textContent=String(selected.length);tray.classList.toggle('is-visible',selected.length>0);document.querySelectorAll('[data-select]').forEach(function(button){button.setAttribute('aria-pressed',String(selected.indexOf(button.dataset.select)>=0));button.textContent=selected.indexOf(button.dataset.select)>=0?'移出收藏 '+button.dataset.select:'加入收藏 '+button.dataset.select})}
      document.querySelectorAll('[data-select]').forEach(function(button){button.addEventListener('click',function(){var value=button.dataset.select;var index=selected.indexOf(value);if(index>=0){selected.splice(index,1)}else if(selected.length<6){selected.push(value)}else{message.textContent='收藏袋最多带走 6 幅作品';toast.classList.add('is-visible');return}updateCollection()})});
      function collectionText(){return selected.join(' ')}function copySelection(){if(!selected.length){message.textContent='请先把至少一幅作品加入收藏';toast.classList.add('is-visible');return}var value=collectionText();var done=function(){message.textContent='收藏单已复制：'+value;toast.classList.add('is-visible')};if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(value).then(done,done)}else{var input=document.createElement('textarea');input.value=value;document.body.appendChild(input);input.select();document.execCommand('copy');input.remove();done()}}
      document.getElementById('copy-selection').addEventListener('click',copySelection);
      document.getElementById('review-collection').addEventListener('click',function(){document.getElementById('exit').scrollIntoView({behavior:reduced?'auto':'smooth'})});document.getElementById('finish-visit').addEventListener('click',copySelection);
      var viewer=document.getElementById('viewer');var viewerImage=viewer.querySelector('.viewer-image');var viewerCaption=viewer.querySelector('.viewer-caption');
      document.querySelectorAll('[data-open]').forEach(function(button){button.addEventListener('click',function(){var item=byId[button.dataset.open];viewerImage.src=item.image;viewerImage.alt='#'+item.number_text+' '+item.label;viewerCaption.textContent='#'+item.number_text+' · '+item.label;viewer.showModal()})});viewer.querySelector('.viewer-close').addEventListener('click',function(){viewer.close()});viewer.addEventListener('click',function(event){if(event.target===viewer)viewer.close()});
      document.addEventListener('keydown',function(event){if(event.target.matches('button,a,input,textarea,select'))return;var active=rooms.findIndex(function(room){return room.classList.contains('is-active')});if(event.key==='ArrowDown'||event.key==='ArrowRight'){rooms[Math.min(active+1,rooms.length-1)].scrollIntoView({behavior:reduced?'auto':'smooth'});event.preventDefault()}if(event.key==='ArrowUp'||event.key==='ArrowLeft'){rooms[Math.max(active-1,0)].scrollIntoView({behavior:reduced?'auto':'smooth'});event.preventDefault()}});
      var ticking=false;function onScroll(){updateProgress();if(!reduced&&!ticking){requestAnimationFrame(function(){rooms.forEach(function(room){var rect=room.getBoundingClientRect();if(rect.bottom>0&&rect.top<innerHeight){var drift=(rect.top/innerHeight-.5)*-18;room.style.setProperty('--drift',drift+'px')}});ticking=false});ticking=true}}addEventListener('scroll',onScroll,{passive:true});addEventListener('resize',function(){updateProgress();fitTitles()});updateProgress();fitTitles();
    }());
  </script>
</body>
</html>'''


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("delivery", type=Path)
    args = parser.parse_args()
    output, manifest = build(args.delivery)
    print(f"PASS: immersive gallery -> {output}")
    print(f"PASS: gallery manifest -> {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
