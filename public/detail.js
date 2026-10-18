"use strict";

// Character detail page and collection views. Uses the shared API/render helpers in app.js.
const DetailUI = (() => {
  const TIERS = [["common", "ทั่วไป"], ["rare", "หายาก"], ["legend", "ตำนาน"]];
  const tierOf = milestone => milestone.tier || (milestone.threshold <= 1 ? "common" : milestone.threshold <= 3 ? "rare" : "legend");

  function collection(character) {
    const entries = state.data.gallery.filter(item => item.character_id === character.id);
    const items = state.data.milestones.map(milestone => {
      const entry = entries.find(item => item.milestone_id === milestone.id);
      return {milestone, entry, tier: tierOf(milestone), open: Boolean(entry), src: momentArt(entry?.character || character, milestone)};
    });
    for (const scene of character.scenes || []) {
      const open = entries.some(item => item.milestone_id === `scene:${scene.id}`);
      items.push({scene, tier: scene.tier, open, src: `/media/${scene.media_id}`,
        milestone: {id: `scene:${scene.id}`, title: scene.title || scene.description, threshold: scene.min_turns}});
    }
    const owned = items.filter(item => item.open).length;
    return {items, owned, total: items.length, percent: items.length ? Math.round(owned / items.length * 100) : 0};
  }

  function tile(character, item) {
    const {milestone} = item;
    if (item.scene) {
      return item.open
        ? `<button class="tc-tile" data-action="view-scene" data-id="${character.id}" data-scene="${item.scene.id}" aria-label="ดูภาพ ${esc(item.scene.title || item.scene.description)}"><img src="${item.src}" alt="${esc(item.scene.description)}" loading="lazy">${item.scene.title ? `<span class="tc-tile-label">${esc(item.scene.title)}</span>` : ""}</button>`
        : `<button class="tc-tile locked tier-${item.tier}" data-action="locked-scene" aria-label="ภาพที่ยังล็อก · ปลดล็อกเมื่อเรื่องราวไปถึงฉากนี้"><img src="${item.src}" alt="" loading="lazy">${icon("lock")}<small>ฉากพิเศษ</small></button>`;
    }
    return item.open
      ? `<button class="tc-tile" data-action="view-moment" data-character="${character.id}" data-milestone="${milestone.id}" aria-label="ดูภาพ ${esc(milestone.title)}"><img src="${item.src}" alt="${esc(milestone.title)}" loading="lazy"></button>`
      : `<button class="tc-tile locked tier-${item.tier}" data-action="locked-moment" aria-label="ภาพที่ยังล็อก · คุยครบ ${milestone.threshold} รอบ"><img src="${item.src}" alt="" loading="lazy">${icon("lock")}<small>คุยครบ ${milestone.threshold} รอบ</small></button>`;
  }

  function page() {
    const detail = state.detail;
    const character = state.data.characters.find(item => item.id === detail.id);
    if (!character) return `<div class="page">${empty("ไม่พบตัวละคร", "ตัวละครนี้อาจถูกลบไปแล้ว", "navigate", "กลับไปหน้าค้นหา", "people").replace('data-action="navigate"', 'data-action="navigate" data-view="discover"')}</div>`;
    const data = collection(character);
    const slides = [art(character), ...data.items.filter(item => item.open).map(item => item.src)];
    const slide = ((detail.slide % slides.length) + slides.length) % slides.length;
    const room = state.data.rooms.find(item => item.character_id === character.id);
    const visible = data.items.filter(item => (detail.tab === "all" || item.tier === detail.tab) && (detail.chip === "all" || (detail.chip === "owned") === item.open));
    const groups = TIERS.map(([tier, label]) => [tier, label, visible.filter(item => item.tier === tier)]).filter(([, , items]) => items.length);
    const tags = (character.tags || []).map(tag => `<span class="tc-tag">#${esc(tag.replace(/^#/, ""))}</span>`).join("");
    return `<div class="tc-detail">
      <header class="tc-detail-top"><button class="tc-icon" data-action="detail-back" aria-label="ย้อนกลับ">${icon("chevron")}</button><span class="tc-stat" title="คอลเลกชันที่สะสมแล้ว">${icon("heart")}${data.percent}%</span></header>
      <section class="tc-hero" aria-label="ภาพตัวละคร"><img src="${slides[slide]}" alt="${esc(character.name)}">${slides.length > 1 ? `<button class="tc-nav prev" data-action="detail-slide" data-dir="-1" aria-label="ภาพก่อนหน้า">${icon("chevron")}</button><button class="tc-nav next" data-action="detail-slide" data-dir="1" aria-label="ภาพถัดไป">${icon("chevron")}</button><div class="tc-dots">${slides.map((_, i) => `<span class="${i === slide ? "on" : ""}"></span>`).join("")}</div>` : ""}</section>
      <h1 class="tc-name">${esc(character.name)}</h1>
      <p class="tc-tagline">${esc(character.subtitle || character.description)}</p>
      <div class="tc-tags">${tags}<span class="tc-tag">#${character.age} ปี</span></div>
      <section class="tc-card-box tc-progress"><div class="tc-row"><strong>คอลเลกชัน</strong><span class="tc-percent">${icon("heart")}${data.percent}%<small>${data.owned}/${data.total}</small></span></div><div class="tc-bar"><span style="width:${data.percent}%"></span></div>${TIERS.map(([tier, label]) => { const items = data.items.filter(item => item.tier === tier); return `<div class="tc-row tier-${tier}"><span>${label}</span><span>${items.filter(item => item.open).length}/${items.length}</span></div>`; }).join("")}</section>
      <section class="tc-intro ${detail.introOpen ? "open" : ""}"><h2>แนะนำตัวละคร</h2><div class="tc-intro-body"><h3>ข้อมูล</h3><p>${esc(character.description)}</p>${character.backstory ? `<p>${esc(character.backstory)}</p>` : ""}<blockquote>${formatText(character.greeting)}</blockquote>${character.tips ? `<h3>เคล็ดลับ</h3><p>${esc(character.tips)}</p>` : ""}${character.relationship ? `<h3>ความสัมพันธ์เริ่มต้น</h3><p>${esc(character.relationship)}</p>` : ""}</div><button class="tc-collapse" data-action="detail-intro" aria-expanded="${detail.introOpen}" aria-label="${detail.introOpen ? "ย่อ" : "ดูเพิ่มเติม"}">${icon("chevron")}</button></section>
      <section class="tc-gallery"><h2>คอลเลกชัน</h2>
        <div class="tc-tabs" role="tablist">${[["all", "ทั้งหมด"], ...TIERS].map(([id, label]) => `<button role="tab" class="${detail.tab === id ? "active" : ""}" aria-selected="${detail.tab === id}" data-action="detail-tab" data-tab="${id}">${label}</button>`).join("")}</div>
        <div class="tc-chips">${[["all", "ทั้งหมด", data.total], ["owned", "มีสะสมแล้ว", data.owned], ["locked", "ติดล็อก", data.total - data.owned]].map(([id, label, count]) => `<button class="${detail.chip === id ? "active" : ""}" aria-pressed="${detail.chip === id}" data-action="detail-chip" data-chip="${id}">${label} <b>${count}</b></button>`).join("")}</div>
        ${groups.length ? groups.map(([tier, label, items]) => `<div class="tc-group tier-${tier}"><div class="tc-group-head"><span>${label}</span></div><div class="tc-grid">${items.map(item => tile(character, item)).join("")}</div></div>`).join("") : `<p class="tc-empty">ไม่มีภาพในหมวดนี้</p>`}
      </section>
      <div class="tc-cta"><button class="tc-cta-button" data-action="start-chat" data-id="${character.id}" ${character.archived ? "disabled" : ""}>${character.archived ? "ตัวละครอยู่ในคลัง" : room ? "สนทนาต่อ" : "เริ่มสนทนา"}</button></div>
    </div>`;
  }

  function collectionPage() {
    const characters = state.data.characters.filter(item => item.custom && !item.archived);
    const owned = characters.reduce((sum, character) => sum + collection(character).owned, 0);
    const total = characters.reduce((sum, character) => sum + collection(character).total, 0);
    return `<div class="page">${pageHeading("คอลเลกชัน", `สะสมแล้ว ${owned} จาก ${total} ภาพ · คุยกับตัวละครเพื่อปลดล็อกภาพใหม่`, false)}
      <div class="tc-collection-grid">${characters.map(character => { const data = collection(character); return `<button class="tc-collection-card" data-action="open-character" data-id="${character.id}"><img src="${art(character)}" alt="" loading="lazy"><span class="tc-collection-meta"><strong>${esc(character.name)}</strong><span class="tc-percent">${icon("heart")}${data.percent}%<small>${data.owned}/${data.total}</small></span><span class="tc-bar"><span style="width:${data.percent}%"></span></span></span></button>`; }).join("")}</div></div>`;
  }

  async function action(element) {
    const detail = state.detail;
    switch (element.dataset.action) {
      case "open-character": case "character-details":
        if ($("#modal").open) $("#modal").close();
        await navigate("character", element.dataset.id); return true;
      case "detail-back": await navigate(state.detailFrom || "discover"); return true;
      case "detail-slide": detail.slide += Number(element.dataset.dir); render(); return true;
      case "detail-tab": detail.tab = element.dataset.tab; render(); return true;
      case "detail-chip": detail.chip = element.dataset.chip; render(); return true;
      case "detail-intro": detail.introOpen = !detail.introOpen; render(); return true;
      case "view-scene": {
        const character = state.data.characters.find(item => item.id === element.dataset.id);
        const scene = character?.scenes?.find(item => item.id === element.dataset.scene);
        if (scene) openModal(esc(scene.title ? `${scene.title} · ${character.name}` : character.name), `<img class="modal-scene" src="/media/${scene.media_id}" alt="${esc(scene.description)}"><p>${esc(scene.description)}</p><div class="form-actions"><button class="primary" data-action="close-modal">ปิด</button></div>`);
        return true;
      }
      case "locked-scene": toast("ภาพนี้จะปลดล็อกเมื่อเรื่องราวดำเนินไปถึงฉากที่ตรงกัน"); return true;
      default: return false;
    }
  }

  return {page, collectionPage, action, collection};
})();
