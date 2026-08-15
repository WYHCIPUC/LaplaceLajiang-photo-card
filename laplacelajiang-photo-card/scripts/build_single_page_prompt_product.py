"""Build a buyer-facing, fully self-contained prompt product as one offline HTML file."""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
from datetime import date
from pathlib import Path

from PIL import Image


PLATFORM_LABELS = ("通用", "豆包", "Kimi", "千问")
INTENSITY_LABELS = ("保真优先", "平衡推荐", "强烈实验")


def image_data_uri(path: Path, max_size: tuple[int, int], quality: int) -> str:
    with Image.open(path) as source:
        image = source.convert("RGB")
        image.thumbnail(max_size, Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=quality, optimize=True, progressive=True)
    return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def load_product(source: Path) -> list[dict]:
    records = json.loads((source / "prompts.json").read_text(encoding="utf-8"))
    if len(records) != 24:
        raise SystemExit(f"expected 24 styles, found {len(records)}")
    result = []
    for record in records:
        if tuple(record["prompts"]) != PLATFORM_LABELS:
            raise SystemExit(f"platform order mismatch: {record['id']}")
        if any(tuple(record["prompts"][platform]) != INTENSITY_LABELS for platform in PLATFORM_LABELS):
            raise SystemExit(f"intensity order mismatch: {record['id']}")
        sample = source / "样图示例" / record["file"]
        if not sample.is_file():
            raise SystemExit(f"missing sample: {sample}")
        item = dict(record)
        item["image"] = image_data_uri(sample, (720, 960), 82)
        result.append(item)
    return result


def build_page(records: list[dict], output: Path) -> None:
    payload = json.dumps(records, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    generated = date.today().isoformat()
    page = f'''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light">
<title>镜语廿四式 · 风格配方馆</title>
<style>
:root{{--paper:#f5f0e8;--surface:#fffdf8;--ink:#251b17;--muted:#76675d;--line:#d8c9ba;--accent:#9b4635;--dark:#38231d;--ok:#2f6a50}}
*{{box-sizing:border-box}}html{{scroll-behavior:smooth}}body{{margin:0;overflow-x:hidden;background:linear-gradient(180deg,#e9dfd2 0,#f7f2ea 18rem);color:var(--ink);font-family:"Microsoft YaHei","PingFang SC",system-ui,sans-serif}}
button,select{{font:inherit}}button{{cursor:pointer}}.shell{{width:min(1440px,calc(100% - 32px));margin:auto}}
.hero{{padding:52px 0 30px}}.eyebrow{{font-size:12px;letter-spacing:.16em;color:var(--accent);font-weight:800}}h1{{font-family:Georgia,"Microsoft YaHei",serif;font-size:clamp(40px,6vw,78px);line-height:1.02;margin:12px 0 18px;letter-spacing:-.05em}}.lead{{max-width:780px;color:var(--muted);font-size:18px;line-height:1.8;margin:0}}.facts{{display:flex;gap:10px;flex-wrap:wrap;margin-top:24px}}.pill{{border:1px solid #cdb9a6;background:#fff9ef;padding:9px 13px;border-radius:999px;color:#5e493d;font-size:13px}}
.how{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:12px 0 28px}}.step{{background:#fff9f0;border:1px solid var(--line);border-radius:16px;padding:18px;line-height:1.65}}.step b{{display:block;color:var(--accent);font-size:13px;margin-bottom:4px}}
.toolbar{{position:sticky;top:0;z-index:20;margin-inline:calc((100vw - min(1440px,calc(100vw - 32px)))/-2);padding:12px max(16px,calc((100vw - min(1440px,calc(100vw - 32px)))/2));display:flex;align-items:center;gap:10px;flex-wrap:wrap;background:#f5f0e8ee;backdrop-filter:blur(18px);border-block:1px solid #d6c5b5;box-shadow:0 8px 24px #5d35220c}}label{{display:flex;align-items:center;gap:7px;color:var(--muted);font-size:13px}}select,.soft,.primary{{border:1px solid #bda58f;border-radius:999px;padding:10px 15px;background:#fffaf1;color:var(--ink)}}.primary{{background:var(--dark);border-color:var(--dark);color:#fff}}.soft:hover,.primary:hover{{transform:translateY(-1px)}}.count{{margin-left:auto;color:var(--muted);font-size:13px}}
.grid{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:18px;padding:28px 0 68px}}.card{{background:var(--surface);border:1px solid var(--line);border-radius:22px;overflow:hidden;box-shadow:0 16px 45px #58382412;transition:.25s transform,.25s box-shadow}}.card:hover{{transform:translateY(-4px);box-shadow:0 24px 60px #58382420}}.art{{position:relative;aspect-ratio:3/4;background:#dfd3c4;overflow:hidden}}.art img{{width:100%;height:100%;object-fit:cover;display:block}}.number{{position:absolute;top:12px;left:12px;background:#251b17dd;color:white;border-radius:999px;padding:7px 10px;font:700 12px/1 Georgia,serif;backdrop-filter:blur(8px)}}.body{{padding:17px}}h2{{font-size:20px;margin:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}.en{{display:block;color:var(--muted);font:11px/1.4 Georgia,serif;letter-spacing:.08em;text-transform:uppercase;margin-top:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}.hint{{font-size:13px;color:var(--muted);line-height:1.6;margin:12px 0 15px;height:42px;overflow:hidden}}.actions{{display:grid;grid-template-columns:1fr 1fr;gap:8px}}.actions button{{border:1px solid #c7b4a3;background:#fbf4e9;color:#4f382e;border-radius:12px;padding:10px 8px;font-size:12px}}.actions .copy{{grid-column:1/-1;background:var(--dark);border-color:var(--dark);color:white;font-weight:700}}.actions .dual{{color:var(--accent);border-color:#c68f80}}.actions button:hover{{filter:brightness(.96)}}
.drawer,.modal{{position:fixed;inset:0;z-index:50;display:none}}.drawer.open,.modal.open{{display:block}}.shade{{position:absolute;inset:0;background:#251a15aa;backdrop-filter:blur(8px)}}.panel{{position:absolute;right:0;top:0;bottom:0;width:min(620px,100%);background:#fffaf2;padding:28px;overflow:auto;box-shadow:-30px 0 80px #160d0933}}.close{{float:right;border:0;background:#eadfd3;width:38px;height:38px;border-radius:50%;font-size:20px}}.panel h3{{font-size:30px;margin:8px 0 20px}}.panel h4{{margin:26px 0 8px;color:var(--accent)}}.panel p,.panel li{{line-height:1.75;color:#5f5047}}.panel code{{background:#ede2d6;padding:2px 6px;border-radius:6px}}.dialog{{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:min(620px,calc(100% - 28px));max-height:82vh;overflow:auto;background:#fffaf2;border-radius:24px;padding:25px;box-shadow:0 30px 100px #170d0966}}.dialog h3{{font-size:26px;margin:0 0 6px}}.dialog p{{color:var(--muted);line-height:1.7}}.dialog textarea{{width:100%;height:260px;border:1px solid var(--line);border-radius:14px;padding:14px;resize:vertical;background:white;font:13px/1.65 "Microsoft YaHei",sans-serif}}.dialog .row{{display:flex;gap:9px;flex-wrap:wrap;margin-top:12px}}
.toast{{position:fixed;left:50%;bottom:24px;z-index:80;transform:translate(-50%,20px);opacity:0;background:#2d211c;color:white;border-radius:999px;padding:12px 20px;transition:.25s;pointer-events:none;box-shadow:0 14px 40px #1d100d44}}.toast.show{{opacity:1;transform:translate(-50%,0)}}footer{{border-top:1px solid var(--line);padding:28px 0 50px;color:var(--muted);font-size:13px;line-height:1.8}}
@media(max-width:1050px){{.grid{{grid-template-columns:repeat(3,1fr)}}}}@media(max-width:760px){{.shell{{width:min(100% - 20px,1440px)}}.hero{{padding-top:32px}}.how{{grid-template-columns:1fr}}.toolbar{{margin-inline:-10px;padding-inline:10px}}.grid{{grid-template-columns:repeat(2,1fr);gap:10px}}.body{{padding:13px}}h2{{font-size:16px}}.hint{{display:none}}.actions{{grid-template-columns:1fr}}.actions button,.actions .copy{{grid-column:1}}.count{{width:100%;margin:0}}}}@media(max-width:430px){{.grid{{grid-template-columns:1fr}}}}
@media(prefers-reduced-motion:reduce){{*{{scroll-behavior:auto!important;transition:none!important}}}}
</style>
</head>
<body>
<div class="shell">
<header class="hero">
  <div class="eyebrow">镜语廿四式 · MIRROR LANGUAGE XXIV</div>
  <h1>把一张照片，<br>练成二十四种观看。</h1>
  <p class="lead">24 种照片美化与视觉风格，适配豆包、Kimi、千问及其他支持参考图编辑的平台。无需安装任何工具：选择平台和强度，找到喜欢的样式，点击复制即可。它可以独立使用，也是“廿四境 · 私人影像展”的附属风格配方馆。</p>
  <div class="facts"><span class="pill">24 种风格</span><span class="pill">4 套平台适配</span><span class="pill">3 档强度</span><span class="pill">双参考强风格</span><span class="pill">完全离线单文件</span></div>
</header>
<section class="how" aria-label="使用步骤">
  <div class="step"><b>01 上传原图</b>进入平台的“参考图生成／图片编辑”入口，将自己的照片上传。</div>
  <div class="step"><b>02 复制提示词</b>人物先用“保真优先”，日常照片用“平衡推荐”，风景与静物可用“强烈实验”。</div>
  <div class="step"><b>03 风格仍太弱</b>下载对应参考图，再复制“双参考强风格”；原图作图 1，参考图作图 2。</div>
</section>
<nav class="toolbar" aria-label="提示词筛选">
  <label>平台<select id="platform"><option>通用</option><option>豆包</option><option>Kimi</option><option>千问</option></select></label>
  <label>强度<select id="intensity"><option>保真优先</option><option selected>平衡推荐</option><option>强烈实验</option></select></label>
  <button class="soft" id="guide">使用须知</button>
  <span class="count">共 24 种 · 所有内容已内嵌</span>
</nav>
<main id="grid" class="grid"></main>
<footer>数字内容版本：{generated}。样图用于说明视觉方向，不保证不同平台得到像素级相同结果。仅上传你有权使用的图片；人物、证件、地址、聊天截图及商业机密请先确认平台隐私规则。本商品不包含平台会员、额度、账号或代生成服务。授权为购买者本人单人使用：你可按所用平台条款商用自己生成的成品，但不可转售、分享、拆包二次上架本网页、提示词或内嵌样图，也不可将其部署为收费代生成服务。</footer>
</div>

<aside class="drawer" id="drawer" aria-hidden="true"><div class="shade" data-close></div><div class="panel"><button class="close" data-close aria-label="关闭">×</button>
<div class="eyebrow">使用须知</div><h3>先看这五点就够了</h3>
<h4>怎么选强度</h4><p><b>保真优先</b>适合人物、纪念照和主体不能重画的图片；<b>平衡推荐</b>适合大多数日常照片；<b>强烈实验</b>适合风景、建筑、静物和需要明显版式变化的图片。</p>
<h4>平台必须能真正出图</h4><p>普通“看图问答”可能只会描述图片。请切换到明确标注参考图、图生图或图片编辑的模式。Kimi 通常需要可实际生成图片的创意设计类插件。</p>
<h4>双参考怎么用</h4><ol><li>点击卡片的“下载参考图”。</li><li>在平台同时上传自己的原图和下载的参考图。</li><li>按上传顺序让自己的原图成为图 1、参考图成为图 2。</li><li>点击“双参考强风格”复制提示词并发送。</li></ol>
<h4>失败怎么修</h4><p>不要重写整段提示词。直接点对应卡片的“风格不够”“出现文字”或“主体跑偏”，把复制出的修复词接着发给平台。</p>
<h4>授权与隐私</h4><p>你必须拥有输入图片的使用权。生成结果是否可商用仍受所用平台条款、素材权利和当地法律约束。本网页可离线使用，不会主动上传或收集你的图片；真正生成时，图片会交给你选择的平台处理。</p><p>本商品授权购买者本人单人使用。允许商用你自己生成的最终图片；禁止转售、分享、拆包二次上架本网页、提示词或样图，也禁止把本商品部署成收费代生成服务。</p>
</div></aside>

<div class="modal" id="modal" aria-hidden="true"><div class="shade" data-modal-close></div><div class="dialog"><button class="close" data-modal-close aria-label="关闭">×</button><div class="eyebrow" id="modalKicker"></div><h3 id="modalTitle"></h3><p id="modalNote"></p><textarea id="prompt" readonly></textarea><div class="row"><button class="primary" id="copyModal">复制这段提示词</button><button class="soft" data-modal-close>关闭</button></div></div></div>
<div class="toast" id="toast" role="status"></div>
<script>
const DATA={payload};
const $=s=>document.querySelector(s), grid=$('#grid'), platform=$('#platform'), intensity=$('#intensity'), toast=$('#toast'), modal=$('#modal'), promptBox=$('#prompt');
const descriptions={{"fashion-sketch":"暖白纸、石墨线与编辑摄影的轻盈融合","retro-travel-collage":"旧纸裁片与旅行刊物式记忆拼贴","sparse-visual-abstraction":"以轮廓、方向与负空间完成稀疏抽象","editorial-memory-panel":"主照片与柔和记忆色面板的安静编排","structured-scene-narrative":"以同源局部构成清晰的场景档案","paper-collage-halftone":"撕纸、网点与套印色形成手工封面感","infographic-editorial":"只解释画面真实关系的无字信息设计","poetic-white-paper":"大面积白纸与轻柔手绘的诗性复原","eastern-silk-cinema":"绢丝、矿物色与墨洗景深的东方静帧","handdrawn-diary-storyboard":"同一瞬间的温暖手账分镜","photo-abstraction-study":"从摄影结构提炼现代几何秩序","photo-memory-editorial":"清晰主图与同源记忆碎片的竖版编辑页","vision-director-board":"英雄画面、色票与材质样本的视觉方案板","halftone-broll-frame":"带运动方向的胶片半调关键画面","data-story-poster":"将真实空间关系转译为无字数据海报","prompt-styleboard":"同一照片的主样式、局部、色彩与材质试验","scene-card-archive":"专业影视场景的主图与细节归档","revival-sketch-sheet":"照片碎片向石墨与淡彩自然延伸","celestial-xianxia-still":"不新增实体的东方天境氛围提升","shot-recipe-keyframe":"建立镜头与同源细节帧的电影方案","classical-poem-silk-poster":"无文字的绢本留白与朱砂视觉锚点","handdrawn-diary-page":"彩铅、石墨与透明水彩的私人手绘页","one-frame-metaphor":"只用原图关系形成单一克制隐喻","minimal-zine-poster":"极大留白、小型锚点与孔版印刷缺陷"}};
function flash(message){{toast.textContent=message;toast.classList.add('show');clearTimeout(flash.t);flash.t=setTimeout(()=>toast.classList.remove('show'),1700)}}
function legacyCopy(value){{const t=document.createElement('textarea');t.value=value;t.style.position='fixed';t.style.opacity='0';document.body.appendChild(t);t.select();document.execCommand('copy');t.remove()}}
async function copy(value,message='提示词已复制'){{try{{await navigator.clipboard.writeText(value)}}catch(e){{legacyCopy(value)}}flash(message)}}
function downloadImage(item){{const a=document.createElement('a');a.href=item.image;a.download=`${{item.number}}-${{item.id}}-风格参考.jpg`;a.click();flash('参考图已下载')}}
function openPrompt(item,kind){{let value,title,note;if(kind==='main'){{value=item.prompts[platform.value][intensity.value];title=`${{item.number}} ${{item.zh}}`;note=`${{platform.value}} · ${{intensity.value}} · 上传自己的原图后发送`}}else if(kind==='dual'){{value=item.dual_prompts[platform.value];title=`${{item.number}} 双参考强风格`;note='请同时上传自己的原图（图 1）和下载的本编号参考图（图 2）'}}else{{value=item.repairs[kind];title=kind;note='在上一张结果不满意时，接着发送这段修复词'}}promptBox.value=value;$('#modalKicker').textContent=item.en;$('#modalTitle').textContent=title;$('#modalNote').textContent=note;modal.classList.add('open');modal.setAttribute('aria-hidden','false')}}
function render(){{grid.innerHTML=DATA.map(x=>`<article class="card"><div class="art"><img loading="lazy" src="${{x.image}}" alt="${{x.number}} ${{x.zh}} 样图"><span class="number">${{x.number}}</span></div><div class="body"><h2>${{x.zh}}</h2><small class="en">${{x.en}}</small><p class="hint">${{descriptions[x.id]||''}}</p><div class="actions"><button class="copy" data-action="main" data-id="${{x.id}}">复制当前提示词</button><button class="dual" data-action="dual" data-id="${{x.id}}">双参考强风格</button><button data-action="download" data-id="${{x.id}}">下载参考图</button><button data-action="风格强化重试" data-id="${{x.id}}">风格不够</button><button data-action="去文字修复" data-id="${{x.id}}">出现文字</button><button data-action="主体保真修复" data-id="${{x.id}}">主体跑偏</button></div></div></article>`).join('')}}
grid.addEventListener('click',e=>{{const b=e.target.closest('[data-action]');if(!b)return;const item=DATA.find(x=>x.id===b.dataset.id),action=b.dataset.action;if(action==='download')downloadImage(item);else if(action==='main')copy(item.prompts[platform.value][intensity.value],`${{platform.value}} · ${{intensity.value}} 已复制`);else if(action==='dual')openPrompt(item,'dual');else openPrompt(item,action)}});
$('#guide').onclick=()=>{{$('#drawer').classList.add('open');$('#drawer').setAttribute('aria-hidden','false')}};document.querySelectorAll('[data-close]').forEach(x=>x.onclick=()=>{{$('#drawer').classList.remove('open');$('#drawer').setAttribute('aria-hidden','true')}});document.querySelectorAll('[data-modal-close]').forEach(x=>x.onclick=()=>{{modal.classList.remove('open');modal.setAttribute('aria-hidden','true')}});$('#copyModal').onclick=()=>copy(promptBox.value);document.addEventListener('keydown',e=>{{if(e.key==='Escape'){{modal.classList.remove('open');$('#drawer').classList.remove('open')}}}});render();
</script>
</body></html>'''
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(page, encoding="utf-8")


def validate(output: Path) -> None:
    content = output.read_text(encoding="utf-8")
    markers = (
        "const DATA=",
        "data:image/jpeg;base64,",
        "双参考强风格",
        "下载参考图",
        "平台必须能真正出图",
        "授权与隐私",
        "本网页可离线使用",
        "镜语廿四式",
        "购买者本人单人使用",
    )
    missing = [marker for marker in markers if marker not in content]
    if missing:
        raise SystemExit(f"single page missing markers: {missing}")
    if content.count("data:image/jpeg;base64,") != 24:
        raise SystemExit("single page must contain exactly 24 embedded sample images")
    if not (300_000 <= output.stat().st_size <= 20_000_000):
        raise SystemExit(f"unexpected single page size: {output.stat().st_size}")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    root.add_argument("--source-pack", type=Path, required=True)
    root.add_argument("--output", type=Path, required=True)
    return root


def main() -> None:
    args = parser().parse_args()
    records = load_product(args.source_pack.resolve())
    build_page(records, args.output.resolve())
    validate(args.output.resolve())
    digest = hashlib.sha256(args.output.read_bytes()).hexdigest().upper()
    print(f"PASS: single-page prompt product -> {args.output.resolve()}")
    print(f"PASS: 24 embedded samples, 456 prompts, sha256={digest}")


if __name__ == "__main__":
    main()
