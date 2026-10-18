"""Build original vector illustrations. No network assets or image dependencies."""
from pathlib import Path
import random

OUT = Path(__file__).resolve().parents[1] / "public" / "assets"
OUT.mkdir(parents=True, exist_ok=True)

PALETTES = {
    "luna": ("#302e52", "#847095", "#c6b8e6", "#ede2da", "#6d5b9a", "#eac8c2"),
    "kael": ("#182f46", "#568193", "#263a53", "#273d57", "#92bbd2", "#d0b6ab"),
    "mira": ("#4e3938", "#c49373", "#834d3e", "#556c5e", "#69463e", "#edc6ad"),
    "ren": ("#293d3c", "#819887", "#333b3a", "#705f51", "#8c9a84", "#ddbfaa"),
}


def stars(seed, color="#f5e6cc", count=34):
    rng = random.Random(seed)
    return "".join(f'<circle cx="{rng.randint(20,580)}" cy="{rng.randint(15,410)}" r="{rng.choice([1,1.5,2])}" fill="{color}" opacity="{rng.uniform(.25,.8):.2f}"/>' for _ in range(count))


def defs(bg, mid, hair, clothes, eye, skin):
    return f'''<defs>
      <linearGradient id="bg" x2=".7" y2="1"><stop stop-color="{bg}"/><stop offset="1" stop-color="{mid}"/></linearGradient>
      <linearGradient id="hair" x2=".9" y2="1"><stop stop-color="{hair}"/><stop offset="1" stop-color="{bg}"/></linearGradient>
      <linearGradient id="coat" x2="1" y2="1"><stop stop-color="{clothes}"/><stop offset="1" stop-color="{bg}"/></linearGradient>
      <linearGradient id="skin" x2=".8" y2="1"><stop stop-color="{skin}"/><stop offset="1" stop-color="{skin}" stop-opacity=".7"/></linearGradient>
      <radialGradient id="glow"><stop stop-color="#f9ddbe" stop-opacity=".5"/><stop offset="1" stop-color="#f9ddbe" stop-opacity="0"/></radialGradient>
      <linearGradient id="shade" x2="0" y2="1"><stop stop-color="{bg}" stop-opacity="0"/><stop offset="1" stop-color="{bg}" stop-opacity=".8"/></linearGradient>
      <filter id="soft"><feGaussianBlur stdDeviation="15"/></filter>
    </defs>'''


def background(name, bg, mid):
    shared = f'<rect width="600" height="760" fill="url(#bg)"/>{stars(name)}<circle cx="455" cy="150" r="140" fill="url(#glow)"/>'
    if name == "luna":
        return shared + '''<path d="M49 554V187a201 201 0 0 1 402 0v367" fill="#242840" stroke="#c1a9c4" stroke-opacity=".3" stroke-width="9"/>
        <path d="M249 22v523M45 258h410M45 413h410" stroke="#d4b3c9" stroke-opacity=".16" stroke-width="5"/>
        <circle cx="352" cy="139" r="50" fill="#efdfcc" opacity=".9"/><circle cx="370" cy="125" r="45" fill="#282c46"/>
        <path d="M60 437h382v107H60z" fill="#36364d"/><path d="M72 434v-49h35v49m10 0v-81h41v81m179 0v-63h27v63m12 0v-92h42v92" fill="#777187" opacity=".4"/>
        <path d="M486 0v760M511 0v760" stroke="#c4acbe" stroke-opacity=".12" stroke-width="2"/>
        <path d="M474 59c-26 50 39 60 7 114s33 80-1 145" fill="none" stroke="#8d9b80" stroke-width="4"/>
        <g fill="#8b9b85"><ellipse cx="469" cy="97" rx="22" ry="9" transform="rotate(30 469 97)"/><ellipse cx="493" cy="149" rx="23" ry="10" transform="rotate(-25 493 149)"/><ellipse cx="472" cy="210" rx="20" ry="9" transform="rotate(30 472 210)"/></g>'''
    if name == "kael":
        return shared + '''<circle cx="460" cy="123" r="51" fill="#c7d7dd" opacity=".8"/><circle cx="439" cy="106" r="46" fill="#264056"/>
        <path d="M0 454 108 291l90 123 105-211 143 223 75-112 79 145v301H0" fill="#263f52"/>
        <path d="m0 510 132-116 129 97 134-145 205 158v256H0" fill="#213345"/>
        <path d="M0 586c122-75 229 12 337-19s163-41 263-5v198H0" fill="#1a2c40"/>
        <path d="m70 125 59 32 56-55 63 38 70-53" fill="none" stroke="#b8d3e0" stroke-opacity=".35"/>
        <g fill="#e1ecdd"><circle cx="70" cy="125" r="3"/><circle cx="129" cy="157" r="3"/><circle cx="185" cy="102" r="4"/><circle cx="248" cy="140" r="3"/><circle cx="318" cy="87" r="3"/></g>'''
    if name == "mira":
        return shared + '''<rect x="21" y="74" width="361" height="451" rx="6" fill="#d0b1a0" opacity=".14"/>
        <rect x="34" y="87" width="335" height="425" fill="#626570"/><path d="M202 87v425M34 299h335" stroke="#b9957a" stroke-width="9"/>
        <path d="M52 405h298v107H52" fill="#50505a"/><path d="M60 406V327h50v79m15 0v-125h52v125m69 0V301h33v105m20 0V267h46v139" fill="#77737c"/>
        <path d="m65 132-10 70m77-75-12 91m113-88-12 72m91-68-12 109m-67 90-12 77m-124-93-8 64" stroke="#d5d5d1" stroke-opacity=".23" stroke-width="2"/>
        <path d="M462 0v123" stroke="#b09b7f" stroke-width="3"/><path d="m417 152 22-41h46l22 41Z" fill="#e0b280"/><ellipse cx="462" cy="154" rx="45" ry="8" fill="#f4dcaa"/>
        <circle cx="462" cy="181" r="85" fill="url(#glow)"/>
        <rect x="414" y="333" width="130" height="92" rx="4" fill="#4e594c" stroke="#c7b58c" stroke-opacity=".4"/>
        <path d="M437 358h81m-81 17h49m-49 17h66" stroke="#e0d6bb" opacity=".4" stroke-linecap="round"/>'''
    return shared + '''<path d="M22 59h207v509H22zM390 59h185v509H390z" fill="#253a36" stroke="#9a9f85" stroke-opacity=".4" stroke-width="4"/>
    <path d="M22 195h207M22 329h207M22 463h207M390 195h185M390 329h185M390 463h185" stroke="#aaa78b" stroke-width="5" opacity=".3"/>
    <g fill="#aeaa8a" opacity=".5"><path d="M35 92h18v99H35zm24 12h24v87H59zm30-27h15v114H89zm24 13h29v101h-29zm34 17h16v84h-16zm21-28h20v112h-20zm25 10h20v102h-20z"/>
    <path d="M403 98h21v93h-21zm27-14h28v107h-28zm35 25h19v82h-19zm27-29h22v111h-22zm30 22h37v89h-37z"/>
    <path d="M35 224h29v102H35zm34 19h21v83H69zm28-23h18v106H97zm25 13h37v93h-37zm44-14h19v107h-19zm26 20h23v87h-23z"/>
    <path d="M402 225h25v101h-25zm31 18h18v83h-18zm23-15h31v98h-31zm38 11h28v87h-28zm33-18h32v105h-32z"/></g>
    <rect x="244" y="42" width="129" height="240" rx="64" fill="#97a58b" opacity=".15"/><circle cx="308" cy="113" r="42" fill="#c9c5a1" opacity=".2"/>'''


def person(name, colors):
    bg, mid, hair, clothes, eye, skin = colors
    woman = name in ("luna", "mira")
    if woman:
        backhair = ('M165 563C123 416 137 234 185 184c56-63 156-54 199 14 44 71 32 235 58 361Z' if name == 'luna'
                    else 'M172 450c-38-46-27-179 5-230 45-78 169-87 217 2 38 71 34 174-4 225Z')
        bangs = ('M167 292c-6-109 76-152 149-117 48 13 76 66 69 122-29-25-51-63-61-95-13 42-44 76-81 93l15-52c-29 30-56 43-91 49Z' if name == 'luna'
                 else 'M168 296c-10-104 63-156 139-133 62 4 99 73 78 133-15-39-29-70-65-91-22 48-72 84-124 86l31-46Z')
        body = f'''<path d="M132 760V601c0-63 55-98 111-116h87c68 19 125 63 129 116v159Z" fill="url(#coat)"/>
        <path d="m243 476-13 37 55 63 58-62-17-41" fill="url(#skin)"/>
        <path d="m230 505 55 58 58-58 22 31-80 70-77-71Z" fill="{clothes}"/>
        <path d="m208 535 77 70 80-69M170 599l-12 161M414 594l17 166" fill="none" stroke="{bg}" stroke-opacity=".25" stroke-width="3"/>
        <path d="M286 607v153" stroke="{bg}" stroke-opacity=".2" stroke-width="2"/>
        <g fill="{bg}" opacity=".35"><circle cx="291" cy="637" r="3"/><circle cx="291" cy="674" r="3"/><circle cx="291" cy="711" r="3"/></g>'''
        if name == "mira":
            body += '''<path d="m211 536 23-17 27 65h56l27-67 21 21-19 66 18 156H208l21-157Z" fill="#3d594d"/><path d="M245 660h83v53h-83z" fill="#496657" stroke="#aec1a0" stroke-opacity=".3"/>'''
    else:
        backhair = 'M172 331c-23-57-20-130 20-167 45-43 129-47 179 1 44 41 45 116 13 169Z'
        bangs = 'M172 285c-24-39-26-77 9-102l-12-31 47 6 27-35 24 24 45-25 6 29 51 10-10 19c48 28 43 75 24 110-13-35-33-69-69-85-33 35-87 49-127 45l22-27Z'
        body = f'''<path d="M100 760V616c0-76 65-117 136-139h93c79 24 139 71 143 139v144Z" fill="url(#coat)"/>
        <path d="m243 471-8 43 49 70 51-70-8-43" fill="url(#skin)"/>
        <path d="m230 503 54 70 52-70 37 37-64 220h-52l-61-221Z" fill="{clothes}"/>
        <path d="m227 502-44 37 34 64-21 18 54 139m85-258 44 37-34 64 21 18-52 139" fill="none" stroke="{mid}" stroke-opacity=".6" stroke-width="4"/>
        <path d="M151 631v129M419 631v129" stroke="{bg}" stroke-width="3" opacity=".5"/>'''
        if name == "kael":
            body += '<path d="m204 516 22-21 60 45 49-44 32 22-30 69-56 27-65-39Z" fill="#7b838a"/><path d="m237 546 88 31-19 137-42-14 6-113Z" fill="#636e7b"/><path d="m314 589 51 153" stroke="#baad8f" opacity=".6" stroke-width="8"/>'
        else:
            body += '<path d="m239 520 45 53 47-53-25 81h-42Z" fill="#e0d4bd"/><path d="m275 570 18 1 10 23-19 105-17-103Z" fill="#444c46"/><path d="M373 628h-35v18h35" fill="none" stroke="#d0bfa3" stroke-opacity=".6" stroke-width="2"/>'
    face = f'''<path d="{backhair}" fill="url(#hair)"/>{body}
    <ellipse cx="173" cy="339" rx="15" ry="27" fill="{skin}"/><ellipse cx="386" cy="339" rx="15" ry="27" fill="{skin}"/>
    <path d="M177 270c0-65 42-97 104-97 65 0 105 41 105 104v82c0 64-58 120-103 128-49-9-106-66-106-128Z" fill="url(#skin)"/>
    <path d="M188 336c15-15 40-15 58-2M317 334c18-15 41-14 56 1" fill="none" stroke="{bg}" stroke-opacity=".7" stroke-width="3" stroke-linecap="round"/>
    <path d="M193 343c14 14 35 15 50-1M321 342c14 14 35 15 48 0" fill="#eee4da"/>
    <ellipse cx="220" cy="345" rx="8" ry="12" fill="{eye}"/><ellipse cx="342" cy="345" rx="8" ry="12" fill="{eye}"/>
    <ellipse cx="221" cy="346" rx="3" ry="8" fill="{bg}"/><ellipse cx="343" cy="346" rx="3" ry="8" fill="{bg}"/>
    <circle cx="223" cy="341" r="2.5" fill="#fff7eb"/><circle cx="345" cy="341" r="2.5" fill="#fff7eb"/>
    <path d="M195 316c16-7 31-7 46-2m79-1c15-5 31-4 45 3" fill="none" stroke="{hair if name != 'luna' else '#887799'}" stroke-width="4" stroke-linecap="round"/>
    <path d="m281 352-7 29 12 3" fill="none" stroke="#b7877b" stroke-opacity=".6" stroke-width="2" stroke-linecap="round"/>
    <path d="M260 411q23 13 45-2" fill="none" stroke="#a86f70" stroke-width="2.5" stroke-linecap="round"/>
    <ellipse cx="215" cy="383" rx="22" ry="10" fill="#d68d90" opacity=".18"/><ellipse cx="345" cy="383" rx="22" ry="10" fill="#d68d90" opacity=".18"/>
    <path d="{bangs}" fill="url(#hair)"/>
    <path d="M200 248c32-45 88-73 135-41M187 226c25-48 74-66 116-60" fill="none" stroke="{mid}" stroke-opacity=".25" stroke-width="3" stroke-linecap="round"/>
    '''
    if name == "luna":
        face += '''<path d="M183 294c-12 90-5 172 21 232l-36 54c-22-102-24-207-6-280m211-9c22 78 15 166 41 247l-37-17c-14-77-13-130-16-190" fill="url(#hair)"/>
        <path d="M178 378v31m204-31v31" stroke="#d9c29a" stroke-width="2"/><path d="m178 405 3 8 8 2-8 3-3 9-3-9-8-3 8-2 3-8Zm204 0 3 8 8 2-8 3-3 9-3-9-8-3 8-2 3-8Z" fill="#e0c99e"/>
        <path d="m180 252 21-12 8 15-22 11Z" fill="#d7bd8d"/><path d="m187 243 3 7m6-11 3 7" stroke="#f5e3b9"/>'''
    if name == "ren":
        face += '''<g fill="#d2e0c3" fill-opacity=".05" stroke="#b8b79d" stroke-width="2.5"><circle cx="221" cy="348" r="31"/><circle cx="342" cy="348" r="31"/><path d="M252 345q29-14 59 0m-121-3-15-5m198 5 15-6" fill="none"/></g>'''
    return face


def foreground(name):
    if name == "luna":
        return '''<g><path d="M12 760v-72h130v72" fill="#59665b"/><path d="M76 705 48 562m31 127 38-162m-45 159-48-94m58 84 70-83" stroke="#7f967b" stroke-width="5"/>
        <g fill="#c2a8bd"><circle cx="48" cy="557" r="18"/><circle cx="115" cy="523" r="17"/><circle cx="25" cy="591" r="17"/><circle cx="149" cy="590" r="18"/></g>
        <g fill="#e1c8d4"><circle cx="40" cy="548" r="13"/><circle cx="55" cy="550" r="13"/><circle cx="47" cy="564" r="13"/><circle cx="109" cy="512" r="11"/><circle cx="123" cy="522" r="11"/><circle cx="109" cy="530" r="11"/></g>
        <path d="M500 760v-69h80v69Z" fill="#a39085"/><path d="m540 716-23-118m24 105 35-86m-40 71-48-58" stroke="#6c826a" stroke-width="4"/>
        <g fill="#a2b49a"><ellipse cx="516" cy="622" rx="9" ry="29" transform="rotate(-25 516 622)"/><ellipse cx="566" cy="642" rx="9" ry="29" transform="rotate(30 566 642)"/><ellipse cx="497" cy="648" rx="9" ry="27" transform="rotate(-40 497 648)"/></g></g>'''
    if name == "mira":
        return '''<path d="M0 698h600v62H0" fill="#594239"/><path d="M0 699h600" stroke="#cfa58a" stroke-opacity=".4" stroke-width="5"/>
        <ellipse cx="126" cy="717" rx="65" ry="10" fill="#3b302e"/><path d="M89 641h67v44a33 33 0 0 1-67 0Z" fill="#dfc6a8"/><path d="M156 652c41-7 41 42 0 35" fill="none" stroke="#dfc6a8" stroke-width="9"/>
        <ellipse cx="122" cy="642" rx="33" ry="7" fill="#8b6250"/><path d="M113 623c-15-23 20-27 4-54m20 54c-11-15 16-22 7-39" stroke="#edddc2" stroke-opacity=".4" stroke-width="3" fill="none"/>
        <path d="M457 717v-78h85v78Z" fill="#86917c"/><path d="M500 648v-75m0 48 30-41m-30 34-30-32" stroke="#a2ae8d" stroke-width="5"/><g fill="#a3af90"><ellipse cx="502" cy="569" rx="10" ry="23"/><ellipse cx="529" cy="584" rx="9" ry="22" transform="rotate(35 529 584)"/><ellipse cx="470" cy="585" rx="9" ry="22" transform="rotate(-35 470 585)"/></g>'''
    if name == "ren":
        return '''<path d="M0 711h600v49H0" fill="#394640"/><path d="M44 682h161v26H44z" fill="#8b7964"/><path d="M51 660h148v21H51z" fill="#667366"/><path d="M61 639h126v20H61z" fill="#b09b7a"/>
        <path d="M431 708h129v-9H431zM490 699v-112" stroke="#b8ac84" stroke-width="4"/><path d="m438 597 28-59h52l34 59Z" fill="#aab692"/><ellipse cx="495" cy="598" rx="58" ry="10" fill="#e2d7a7"/><circle cx="495" cy="623" r="80" fill="url(#glow)"/>'''
    return '''<path d="M0 728c54-39 96-28 155 11l56 21H0m600-42c-67-45-120-18-176 42h176" fill="#172d3a"/>
    <path d="m47 735 12-115 10 110m-21-36-20-38m35 16 25-37m470 100-9-132-12 126m7-43 26-29m-28-2-18-46" stroke="#516c6a" stroke-width="3" fill="none"/>
    <path d="m82 654 61-5 14 49-61 6Z" fill="#dccba5" opacity=".8"/><path d="m92 668 38-4m-35 14 42-5m-38 15 24-3" stroke="#777e78" stroke-width="2"/>'''


def portrait(name, scene=None):
    colors = PALETTES[name]
    bg, mid, *_ = colors
    body = defs(*colors) + background(name,bg,mid)
    if scene == "stars":
        body += '<rect width="600" height="760" fill="#17233c" opacity=".3"/>' + stars(name + "night",count=65)
    body += person(name, colors) + foreground(name)
    if scene == "ritual":
        body += '<path d="M357 701h69v-54h-69z" fill="#d5c1ad"/><ellipse cx="391" cy="647" rx="35" ry="8" fill="#8b6b65"/><path d="M427 658c35-7 35 34 0 32" stroke="#d5c1ad" stroke-width="9" fill="none"/>'
    body += '<rect y="650" width="600" height="110" fill="url(#shade)"/>'
    if scene:
        titles = {"first": "FIRST LIGHT", "ritual": "LITTLE RITUALS", "stars": "UNDER THE STARS"}
        body += f'<text x="34" y="719" font-family="Georgia,serif" font-size="22" letter-spacing="3" fill="#f1e7db">{titles[scene]}</text><text x="36" y="742" font-family="Arial,sans-serif" font-size="9" letter-spacing="3" fill="#d3c5cd">{name.upper()} · AN ELYRA MEMORY</text>'
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 760" role="img"><title>{name.title()} — original ELYRA vector illustration</title>{body}</svg>'


for name in PALETTES:
    (OUT / f"{name}.svg").write_text(portrait(name), encoding="utf-8")
    for scene in ("first", "ritual", "stars"):
        (OUT / f"{name}-{scene}.svg").write_text(portrait(name,scene), encoding="utf-8")
(OUT / "favicon.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="16" fill="#24212e"/><path d="m32 7 7 18 18 7-18 7-7 18-7-18-18-7 18-7Z" fill="#c9b6f3"/></svg>',encoding="utf-8")
print(f"Built 17 original SVG assets in {OUT}")
