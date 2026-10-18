"use strict";

const ICONS = {
  compass: '<circle cx="12" cy="12" r="9"/><path d="m16 8-2.5 5.5L8 16l2.5-5.5L16 8Z"/>',
  chat: '<path d="M20 11.5a8 8 0 0 1-8 8H5l-3 2v-10a9 9 0 0 1 18 0Z"/><path d="M8 10h8M8 14h5"/>',
  people: '<circle cx="9" cy="8" r="3"/><path d="M3 20v-2a6 6 0 0 1 12 0v2M16 5a3 3 0 0 1 0 6M17 14a5 5 0 0 1 4 5"/>',
  image: '<rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="8" cy="8" r="1.5"/><path d="m3 17 5-5 4 4 4-6 5 7"/>',
  settings: '<path d="m9 3-1 3-3 1-2 4 2 3v3l4 3 3-1 3 1 4-3v-3l2-3-2-4-3-1-1-3H9Z"/><circle cx="12" cy="12" r="3"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 4 4"/>',
  arrow: '<path d="M5 12h14m-6-6 6 6-6 6"/>',
  chevron: '<path d="m9 5 7 7-7 7"/>',
  heart: '<path d="M20.8 4.8a5.5 5.5 0 0 0-7.8 0L12 6l-1-1.2a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.4a5.5 5.5 0 0 0 0-7.8Z"/>',
  star: '<path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2L12 17.3l-5.6 2.9 1.1-6.2L3 9.6l6.2-.9L12 3Z"/>',
  sparkle: '<path d="m12 3 2.3 6.7L21 12l-6.7 2.3L12 21l-2.3-6.7L3 12l6.7-2.3L12 3Z"/>',
  send: '<path d="m4 4 17 8-17 8 3-8-3-8Zm3 8h14"/>',
  lock: '<rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/><path d="M12 14v3"/>',
  book: '<path d="M12 5c-3-2-6-2-10-1v15c4-1 7-1 10 1 3-2 6-2 10-1V4c-4-1-7-1-10 1Zm0 0v15"/>',
  bookmark: '<path d="M6 3h12v18l-6-4-6 4V3Z"/>',
  close: '<path d="m6 6 12 12M6 18 18 6"/>',
  menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
  refresh: '<path d="M20 7v5h-5M4 17v-5h5"/><path d="M6 6a8 8 0 0 1 13 1l1 5M4 12l1 5a8 8 0 0 0 13 1"/>',
  trash: '<path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7M14 10v7"/>',
  download: '<path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7h.01"/>',
  shield: '<path d="m12 2 8 4v6c0 5-8 10-8 10S4 17 4 12V6l8-4Z"/><path d="m8 12 3 3 5-6"/>',
  cpu: '<rect x="5" y="5" width="14" height="14" rx="3"/><path d="M9 1v4M15 1v4M9 19v4M15 19v4M1 9h4M1 15h4M19 9h4M19 15h4"/><rect x="9" y="9" width="6" height="6" rx="1"/>',
  cloud: '<path d="M6 18a5 5 0 0 1-1-10 7 7 0 0 1 13-1 5.5 5.5 0 0 1 0 11H6Z"/>',
  eye: '<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/>',
};
const icon = name => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[name] || ICONS.sparkle}</svg>`;
const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const $ = selector => document.querySelector(selector);
// getRandomValues also works over LAN HTTP, where crypto.randomUUID is unavailable.
const newId = () => Array.from(crypto.getRandomValues(new Uint8Array(16)), byte => byte.toString(16).padStart(2, "0")).join("");
const art = character => /^[a-f0-9]{64}$/.test(character.portrait_id || "") ? `/media/${character.portrait_id}` : `/assets/${["luna","kael","mira","ren"].includes(character.art) ? character.art : "luna"}.svg`;
const momentArt = (character, milestone) => /^[a-f0-9]{64}$/.test(character.gallery?.[milestone.id] || "") ? `/media/${character.gallery[milestone.id]}` : `/assets/${["luna","kael","mira","ren"].includes(character.art) ? character.art : "luna"}-${milestone.scene}.svg`;
const labels = {demo: "Demo mode", xai: "xAI · Cloud", openai: "OpenAI · Cloud", ollama: "Ollama · Local"};
const genreLabels = {all: "ทั้งหมด", romance: "โรแมนซ์", fantasy: "แฟนตาซี", everyday: "ชีวิตประจำวัน", mystery: "ปริศนา", favorites: "รายการโปรด"};
const state = {view: "discover", data: null, room: null, filter: "all", search: "", galleryFilter: "all", sending: false, settingsDraft: null, modelLists: {}, favorites: new Set(), selectedArt: "luna"};
try { state.favorites = new Set(JSON.parse(localStorage.getItem("elyra-favorites") || "[]")); } catch { /* Browser storage can be unavailable. */ }

async function api(path, data, options = {}) {
  const response = await fetch(path, {method: data === undefined ? "GET" : "POST", headers: {"Content-Type": "application/json", "X-Elyra-Token": state.data?.token || ""}, body: data === undefined ? undefined : JSON.stringify(data), ...options});
  if (!response.ok) {
    const result = await response.json().catch(() => ({}));
    throw new Error(result.error || `ไม่สามารถทำรายการได้ (HTTP ${response.status})`);
  }
  return response.json();
}

function toast(message, error = false) {
  const element = document.createElement("div");
  element.className = `toast${error ? " error" : ""}`;
  element.textContent = message;
  $("#toast-region").append(element);
  setTimeout(() => element.remove(), error ? 7000 : 4200);
}

async function refresh() { state.data = await api("/api/bootstrap"); }
function currentName() { return state.data.settings.displayName || "Storyteller"; }
function cleanPreview(text) { return String(text || "").replace(/\*/g, "").replace(/\s+/g, " "); }
function timeLabel(date) { return new Date(date).toLocaleTimeString("th-TH", {hour: "2-digit", minute: "2-digit"}); }
function button(action, label, type = "primary", symbol = "plus", extra = "") { return `<button class="${type}" data-action="${action}" ${extra}>${symbol ? icon(symbol) : ""}${label}</button>`; }

function shell(content) {
  const data = state.data;
  const nav = [["discover", "compass", "ค้นหา"], ["chats", "chat", "แชต"], ["gallery", "image", "คอลเลกชัน"], ["characters", "people", "ฉัน"]];
  const activeView = state.view === "chat" ? "chats" : state.view === "character" ? state.detailFrom : state.view;
  return `<div class="shell${state.view === "character" ? " detail-view" : state.view === "chat" ? " chat-view" : ""}"><button class="mobile-scrim" data-action="close-sidebar" aria-label="ปิดเมนู"></button>
    <aside class="sidebar"><a href="#discover" class="brand" aria-label="ELYRA หน้าแรก"><span class="brand-mark">✧</span><span class="brand-word">ELYRA</span></a><span class="early-badge">Early Access</span>
      <nav class="nav" aria-label="เมนูหลัก">${nav.map(([view, symbol, label]) => `<button data-action="navigate" data-view="${view}" class="${activeView === view ? "active" : ""}">${icon(symbol)}${label}</button>`).join("")}</nav>
      <div class="sidebar-bottom"><button class="side-link" data-action="create-character">${icon("plus")}สร้างตัวละคร</button>
        <button class="side-link${state.view === "settings" ? " active" : ""}" data-action="navigate" data-view="settings">${icon("settings")}ตั้งค่า</button></div>
    </aside>
    <main class="main"><header class="topbar"><button class="mobile-menu icon-button" data-action="menu" aria-label="เปิดเมนู">${icon("menu")}</button><div><div class="eyebrow">YOUR STORY, YOUR UNIVERSE</div><span class="breadcrumb">${{discover:"ค้นพบโลกใบใหม่", chats:"บทสนทนาของคุณ", characters:"พื้นที่สร้างตัวละคร", gallery:"ความทรงจำที่เก็บไว้", settings:"ตั้งค่าพื้นที่ของคุณ", chat:"เรื่องราวกำลังดำเนินต่อ…", character:"รายละเอียดตัวละคร"}[state.view]}</span></div><div class="top-actions"><label class="search">${icon("search")}<input id="global-search" aria-label="ค้นหาตัวละคร" placeholder="ค้นหาตัวละครหรือเรื่องราว…" value="${esc(state.search)}"><kbd>/</kbd></label><span class="local-badge"><span class="status-dot"></span>LOCAL DEMO</span></div></header>${content}</main></div>`;
}

function pageHeading(title, subtitle, action = true) {
  return `<div class="page-heading"><div><h1>${title}</h1><p>${subtitle}</p></div>${action ? button("create-character", "สร้างตัวละคร", "primary", "plus") : ""}</div>`;
}

function characterCard(character) {
  const favorite = state.favorites.has(character.id);
  return `<article class="character-card tc-card"><button class="tc-card-hit" data-action="open-character" data-id="${character.id}" aria-label="ดูรายละเอียด ${esc(character.name)}"><img src="${art(character)}" alt="" loading="lazy"><span class="tc-card-meta"><strong>${esc(character.name)}</strong><small>${esc(character.subtitle || character.description)}</small></span></button><button class="favorite ${favorite ? "active" : ""}" data-action="favorite" data-id="${character.id}" aria-label="${favorite ? "นำออกจาก" : "เพิ่มใน"}รายการโปรด" aria-pressed="${favorite}">${icon("heart")}</button><div class="card-body">${state.view === "characters" ? `<button class="tc-card-start" data-action="start-chat" data-id="${character.id}">${icon("chat")}คุยเลย</button>` : ""}</div></article>`;
}

function filteredCharacters(customOnly = false) {
  return state.data.characters.filter(character => {
    if (customOnly ? Boolean(character.archived) !== Boolean(state.showArchived) : character.archived) return false;
    const matchSearch = `${character.name} ${character.description} ${character.tags.join(" ")}`.toLowerCase().includes(state.search.toLowerCase());
    const matchFilter = state.filter === "all" || (state.filter === "favorites" ? state.favorites.has(character.id) : character.genre === state.filter);
    return matchSearch && (customOnly ? character.custom : matchFilter);
  });
}

function empty(title, description, action = "", label = "", symbol = "sparkle") {
  return `<div class="empty-state">${icon(symbol)}<h2>${title}</h2><p>${description}</p>${action ? button(action, label, "primary", "plus") : ""}</div>`;
}

function discover() {
  const characters = filteredCharacters();
  return `<div class="page">${pageHeading("ค้นพบเรื่องราวของคุณ", "พบใครสักคนที่ทำให้บทสนทนาธรรมดา… มีความหมายมากกว่าเดิม")}
    ${!state.search ? `<section class="hero"><img class="hero-art" src="/assets/luna.svg" alt="ลูนาในร้านดอกไม้ยามค่ำคืน"><div class="hero-content"><div class="hero-label">A NEW CONNECTION AWAITS <span>FEATURED</span></div><h2>A little conversation.<br><em>An entirely new world.</em></h2><p>ร้านดอกไม้ในคืนฝนตก ชาอุ่น ๆ สักถ้วย<br>และใครบางคนที่พร้อมฟังเรื่องราวของคุณ</p>${button("start-chat", "เริ่มเรื่องราวกับ Luna", "primary", "sparkle", 'data-id="luna"')}</div><div class="hero-feature"><strong>Luna <span>✦</span></strong><small>The keeper of little wonders</small></div><div class="hero-dots" aria-hidden="true"><span></span><span></span><span></span></div></section>` : ""}
    <section><div class="section-heading"><div><h2>${state.search ? `ผลการค้นหา “${esc(state.search)}”` : "ใครจะเป็นเรื่องราวบทต่อไป?"}</h2><small>${state.search ? `${characters.length} ตัวละครที่พบ` : "ตัวละครต่างบุคลิก สำหรับเรื่องราวในแบบของคุณ"}</small></div><span class="eyebrow">FIND YOUR CONNECTION</span></div><div class="filters" role="group" aria-label="ประเภทตัวละคร">${Object.entries(genreLabels).map(([id,label]) => `<button class="filter ${state.filter === id ? "active" : ""}" data-action="filter" data-filter="${id}" aria-pressed="${state.filter === id}">${label}</button>`).join("")}</div><div id="character-results">${characters.length ? `<div class="character-grid">${characters.map(characterCard).join("")}</div>` : empty("ยังไม่พบตัวละคร", "ลองค้นหาด้วยชื่อหรือเลือกประเภทอื่น")}</div></section>
    <section class="continue-section"><div class="section-heading"><div><h2>เรื่องราวที่รอคุณกลับมา</h2><small>กลับไปคุยต่อ จากตรงที่เราค้างไว้</small></div>${state.data.rooms.length ? button("navigate", "ดูบทสนทนาทั้งหมด", "ghost", "arrow", 'data-view="chats"') : ""}</div>${state.data.rooms.length ? `<div class="continue-grid">${state.data.rooms.slice(0, 2).map(roomTile).join("")}</div>` : `<div class="first-story"><span>✧</span><p><strong>เรื่องราวแรกของคุณกำลังรออยู่</strong><br>เลือกตัวละครแล้วเริ่มคุย ความทรงจำจะถูกบันทึกไว้ที่นี่</p>${button("start-chat", "ทักทาย Luna", "secondary", "arrow", 'data-id="luna"')}</div>`}</section>
    <footer class="page-foot"><span>${icon("shield")}พื้นที่ส่วนตัว · ทุกตัวละครเป็น AI · แชตบันทึกบนเครื่องนี้</span><span>Made for your imagination. ✧</span></footer></div>`;
}

function roomTile(room) { return `<button class="continue-card" data-action="open-room" data-id="${room.id}"><img src="${art(room.character)}" alt=""><div><strong>${esc(room.character.name)}</strong><small>${esc(cleanPreview(room.preview))}</small><small>${labels[room.provider]} · ${room.turns} บทสนทนา</small></div>${icon("arrow")}</button>`; }

function chats() {
  return `<div class="page">${pageHeading("บทสนทนาของฉัน", "ทุกเรื่องราวยังอยู่ตรงนี้ พร้อมให้คุณกลับมาสานต่อ", false)}${state.data.rooms.length ? `<div class="continue-grid">${state.data.rooms.map(roomTile).join("")}</div>` : empty("ยังไม่มีบทสนทนา", "เริ่มพูดคุยกับตัวละครที่คุณสนใจ แล้วกลับมาคุยต่อเมื่อไรก็ได้", "navigate", "ค้นพบตัวละคร", "chat").replace('data-action="navigate"', 'data-action="navigate" data-view="discover"')}</div>`;
}

function charactersPage() {
  const characters = filteredCharacters(true);
  return `<div class="page">${pageHeading("ตัวละครของฉัน", "สร้างบุคลิก กำหนดเรื่องราว และให้จินตนาการเริ่มบทสนทนา")}${characters.length ? `<div class="character-grid">${characters.map(characterCard).join("")}</div>` : empty("ใครอยู่ในจินตนาการของคุณ?", "ตั้งชื่อ เลือกบุคลิก เขียนฉากเปิด แล้วทดลองคุยกับตัวละครของคุณ ทุกตัวละครที่สร้างในเดโมเป็นส่วนตัว", "create-character", "สร้างตัวละครแรก", "people")}</div>`;
}

function messageMarkup(message, character) {
  const user = message.role === "user";
  return `<article class="message ${user ? "user" : "assistant"}" data-message-id="${esc(message.id)}">${user ? `<span class="avatar-letter">${esc(currentName().slice(0,1).toUpperCase())}</span>` : `<img src="${art(character)}" alt="">`}<div class="message-body"><div class="message-meta"><strong>${esc(user ? currentName() : character.name)}</strong><span>${message.created_at ? timeLabel(message.created_at) : ""}${!user ? ` · ${message.provider === "demo" ? "SCRIPTED DEMO" : "AI"}` : ""}</span></div><div class="message-text">${formatChat(message.content, user ? "" : character.name)}</div>${message.id ? `<div class="message-tools"><button data-action="remember-message" data-id="${message.id}">${icon("bookmark")}บันทึกความจำ</button></div>` : ""}</div></article>`;
}

function formatText(text) {
  // Only escaped text and bounded inline emphasis. No HTML or Markdown links from models.
  return esc(text).replace(/\*([^*]+)\*/g, "<em>$1</em>");
}

// A side character's line: `Name: "..."` or `Name: ...` (grok often drops the quotes). Name is up to two short
// words; text starting with a digit after the colon ("เวลา: 10 โมง") is not treated as a speaker.
const NPC_LINE = /^([^\s:："“*]{1,24}(?:\s[^\s:："“*]{1,12})?)\s*[:：]\s*(?!\d)(\S[\s\S]*)$/;

function formatChat(text, mainName = "") {
  // *situation* becomes a centered narration line; dialogue paragraphs become bubbles. Side characters' lines get a
  // labelled bubble of their own; the main character's name prefix (if the model adds one) is dropped. Escaped text only.
  return String(text || "").split(/(\*[^*]+\*)/).map(part => {
    if (/^\*[^*]+\*$/.test(part)) return part.slice(1, -1).trim() ? `<p class="narr">${esc(part.slice(1, -1).trim())}</p>` : "";
    return part.split(/\n\s*\n/).map(block => block.trim()).filter(Boolean).map(block => {
      const npc = block.match(NPC_LINE);
      if (!npc) return `<p class="line">${esc(block)}</p>`;
      if (npc[1] === mainName) return `<p class="line">${esc(npc[2])}</p>`;
      return `<p class="line npc"><span class="speaker">${esc(npc[1])}</span>${esc(npc[2])}</p>`;
    }).join("");
  }).join("");
}

function chatPage() {
  const room = state.room;
  if (!room) return `<div class="page">${empty("กำลังเปิดบทสนทนา…", "")}</div>`;
  const character = room.character;
  const unlocked = state.data.milestones.filter(milestone => room.unlocks.includes(milestone.id));
  const current = state.data.characters.find(item => item.id === character.id);
  const picked = (current?.scenes || character.scenes || []).find(item => item.id === room.scene_id);
  // Keep the room's persona snapshot, but show the author's latest uploaded artwork.
  // Scene selection already follows the live character; milestone/portrait fallbacks must too.
  const artwork = current || character;
  const scene = picked ? `/media/${picked.media_id}` : unlocked.length ? momentArt(artwork, unlocked[unlocked.length - 1]) : art(artwork);
  const stats = DetailUI.collection(state.data.characters.find(item => item.id === character.id) || character);
  const progress = Math.min(100, Math.round(room.turns / 6 * 100));
  return `<div class="chat-layout tc-chat${state.chatPeek ? " peek" : ""}"><section class="chat-main"><img class="tc-chat-bg" src="${scene}" alt="">
    <header class="tc-chat-top"><button class="tc-icon" data-action="navigate" data-view="chats" aria-label="กลับไปหน้าแชต">${icon("chevron")}</button><button class="tc-chat-pill" data-action="open-character" data-id="${character.id}" title="ดูคอลเลกชันของ ${esc(character.name)}"><span class="tc-chat-pill-fill" style="width:${stats.percent}%"></span><span class="tc-chat-pill-text">${stats.owned}/${stats.total}</span>${icon("chevron")}</button><button class="tc-chat-round" data-action="toggle-info" aria-label="ข้อมูล ความจำ และการตั้งค่าห้อง">${icon("menu")}</button></header>
    <div class="tc-chat-badges"><span class="tc-chat-round tc-chat-percent" title="ความคืบหน้าเรื่องราว ${room.turns} รอบ">${progress}%</span><button class="tc-chat-round" data-action="chat-peek" aria-pressed="${Boolean(state.chatPeek)}" aria-label="ซ่อนหรือแสดงบทสนทนาเพื่อดูภาพ">${icon("eye")}</button></div>
    <div class="messages" id="messages" aria-label="ข้อความสนทนา">${room.messages.map(message => messageMarkup(message, character)).join("")}</div>
    <div class="composer-area"><div class="tc-chat-chips"><button type="button" class="tc-chip" data-action="insert-situation" title="แทรก * * สำหรับบรรยายสถานการณ์หรือการกระทำ">${icon("sparkle")}สถานการณ์</button></div><form id="chat-form" class="composer"><label class="sr-only" for="chat-input">ข้อความถึง ${esc(character.name)}</label><textarea id="chat-input" placeholder="เขียนข้อความ..." maxlength="4000" rows="1" ${state.sending ? "disabled" : ""}></textarea><button type="submit" aria-label="ส่งข้อความ" ${state.sending ? "disabled" : ""}>${state.sending ? '<span class="spinner"></span>' : icon("send")}</button></form><p class="composer-note">${room.provider === "demo" ? "โหมดจำลอง: คำตอบเขียนไว้ล่วงหน้า" : `${labels[room.provider]} · ${esc(room.model)}`} · ใช้ *ข้อความ* บรรยายสถานการณ์ · Shift + Enter ขึ้นบรรทัดใหม่</p></div></section>
    <aside class="chat-side" id="chat-side"><div class="tc-side-head"><strong>${esc(character.name)}</strong><button class="icon-button" data-action="toggle-info" aria-label="ปิดแผงข้อมูล">${icon("close")}</button></div><div class="tc-side-actions"><select class="engine-select" id="room-provider" aria-label="เลือก AI สำหรับห้องนี้" ${state.sending ? "disabled" : ""}>${Object.entries(labels).map(([id, label]) => `<option value="${id}" ${room.provider === id ? "selected" : ""}>${label}</option>`).join("")}</select><button class="icon-button" data-action="new-chapter" aria-label="เริ่มห้องใหม่" title="เริ่มเรื่องราวใหม่">${icon("refresh")}</button><button class="icon-button" data-action="delete-room" aria-label="ลบบทสนทนานี้" title="ลบบทสนทนา">${icon("trash")}</button></div>${storyPanel(room)}</aside></div>`;
}

function storyPanel(room) {
  const character = room.character;
  const artwork = state.data.characters.find(item => item.id === character.id) || character;
  const progress = Math.min(100, Math.round(room.turns / 6 * 100));
  return `<img class="side-portrait" src="${art(artwork)}" alt="${esc(character.name)}"><span class="eyebrow">YOUR COMPANION</span><h2 class="side-name">${esc(character.name)}</h2><p class="side-description">${esc(character.description)}</p><div class="tag-row">${character.tags.slice(0,2).map(tag=>`<span class="tag">${esc(tag)}</span>`).join("")}</div><div class="side-heading">STORY PROGRESS ${icon("heart")}</div><div class="relationship-title">${room.turns >= 6 ? "ความทรงจำร่วมกัน" : room.turns >= 3 ? "เริ่มคุ้นเคย" : "การพบกันครั้งแรก"}<span>${progress}%</span></div><div class="progress-track"><div class="progress-fill" style="width:${progress}%"></div></div><p class="progress-caption">ความคืบหน้าเดโม · ${room.turns} รอบสนทนา</p><div class="side-heading">ความจำของเรื่องราว<button class="icon-button" data-action="add-memory" aria-label="เพิ่มความจำ">${icon("plus")}</button></div>${room.memories.length ? room.memories.map(memory => `<div class="memory-item"><p>${esc(memory.content)}</p><button data-action="forget" data-id="${memory.id}" aria-label="ลืมความจำนี้">${icon("close")}</button></div>`).join("") : '<p class="side-empty">บันทึกเรื่องสำคัญที่อยากให้ตัวละครจำ<br>ความจำจะใช้เฉพาะในห้องนี้</p>'}${state.data.milestones.length ? `<div class="side-heading">MOMENTS TO COLLECT ${icon("image")}</div>${state.data.milestones.map(milestone => `<div class="milestone-item ${room.unlocks.includes(milestone.id) ? "unlocked" : ""}"><span class="milestone-icon">${icon(room.unlocks.includes(milestone.id) ? "sparkle" : "lock")}</span><div><strong>${milestone.title}</strong><small>${room.unlocks.includes(milestone.id) ? "ปลดล็อกแล้ว · ดูในอัลบั้ม" : `คุยครบ ${milestone.threshold} รอบเพื่อปลดล็อก`}</small></div></div>`).join("")}<div class="notice">ภาพประกอบสำเร็จรูป · ปลดล็อกตามรอบสนทนาในเดโม</div>` : ""}`;
}

function galleryPage() {
  const cards = [];
  for (const character of state.data.characters) {
    for (const milestone of state.data.milestones) {
      const entry = state.data.gallery.find(item => item.character_id === character.id && item.milestone_id === milestone.id);
      if (state.galleryFilter === "unlocked" && !entry) continue;
      cards.push(`<button class="gallery-card ${entry ? "" : "locked"}" data-action="${entry ? "view-moment" : "locked-moment"}" data-character="${character.id}" data-milestone="${milestone.id}"><div class="gallery-image"><img src="${momentArt(entry?.character || character,milestone)}" alt="${entry ? esc(milestone.title + " กับ " + character.name) : "ภาพความทรงจำที่ยังไม่ปลดล็อก"}" loading="lazy">${entry ? `<div class="card-topline"><span class="pill">MOMENT UNLOCKED ✧</span></div>` : `<div class="gallery-lock">${icon("lock")}คุยกับ ${esc(character.name)} ครบ ${milestone.threshold} รอบ</div>`}</div><div class="gallery-info"><h3>${milestone.title}</h3><p>${esc(character.name)} · ${milestone.description}</p><small>${entry ? "เก็บไว้ในความทรงจำแล้ว" : "เรื่องราวนี้ยังรอให้คุณค้นพบ"}</small></div></button>`);
    }
  }
  const unique = new Set(state.data.gallery.map(item=>item.character_id + item.milestone_id)).size;
  return `<div class="page">${pageHeading("อัลบั้มความทรงจำ", `ทุกช่วงเวลามีเรื่องเล่า · ปลดล็อกแล้ว ${unique} จาก ${state.data.characters.length * 3} ภาพ`, false)}<div class="filters"><button class="filter ${state.galleryFilter === "all" ? "active" : ""}" data-action="gallery-filter" data-filter="all">ความทรงจำทั้งหมด</button><button class="filter ${state.galleryFilter === "unlocked" ? "active" : ""}" data-action="gallery-filter" data-filter="unlocked">ปลดล็อกแล้ว</button></div>${cards.length ? `<div class="gallery-grid">${cards.join("")}</div>` : empty("ความทรงจำดี ๆ กำลังรอคุณ", "เริ่มคุยกับตัวละคร 1, 3 และ 6 รอบ เพื่อปลดล็อกภาพประกอบของแต่ละคน", "navigate", "ไปค้นพบตัวละคร", "image").replace('data-action="navigate"', 'data-action="navigate" data-view="discover"')}</div>`;
}

function settingsPage() {
  const draft = state.settingsDraft || structuredClone(state.data.settings);
  state.settingsDraft = draft;
  const provider = draft.provider;
  const models = state.modelLists[provider] || [];
  const configured = state.data.providers[provider]?.configured;
  return `<div class="page">${pageHeading("พื้นที่ของคุณ กติกาของคุณ", "เลือกวิธีเชื่อมต่อ AI และจัดการความเป็นส่วนตัว", false)}<form id="settings-form"><div class="settings-grid"><div><section class="panel"><h2>AI connection</h2><p>เลือกค่าเริ่มต้นสำหรับห้องใหม่ เปลี่ยนโมเดลของห้องเดิมได้จากหน้าแชต</p><div class="provider-options">${[["demo","✧","คำตอบจำลอง · ไม่ใช้ API"],["xai","𝕏","Cloud API"],["openai","◎","Cloud API"],["ollama","◉","ประมวลผลบนเครื่องนี้"]].map(([id,mark,note])=>`<button type="button" class="provider-option ${provider === id ? "active" : ""}" data-action="choose-provider" data-provider="${id}"><span class="provider-icon">${mark}</span><strong>${{demo:"Demo",xai:"xAI",openai:"OpenAI",ollama:"Ollama"}[id]}</strong><small>${note}</small></button>`).join("")}</div>${provider === "demo" ? '<div class="notice"><strong>พร้อมลองใช้งานทันที</strong><br>โหมดนี้ใช้บทสนทนาที่เขียนไว้ล่วงหน้า เพื่อทดลองแชต ความจำ และการปลดล็อกภาพ โดยไม่เรียกโมเดล AI</div>' : `<div class="field"><label for="model-name">โมเดลสำหรับตอบแชต</label><input id="model-name" name="model" list="available-models" placeholder="${provider === "ollama" ? "ชื่อโมเดลที่ดาวน์โหลดไว้ใน Ollama" : "เลือกชื่อโมเดลที่บัญชีคุณใช้งานได้"}" value="${esc(draft.models[provider])}" maxlength="160" autocomplete="off"><datalist id="available-models">${models.map(model=>`<option value="${esc(model)}"></option>`).join("")}</datalist><small>กดตรวจสอบการเชื่อมต่อเพื่อโหลดรายชื่อโมเดล แล้วเลือกโมเดลสำหรับการสนทนา</small><label class="apply-rooms"><input type="checkbox" id="apply-to-rooms" ${draft.applyToRooms ? "checked" : ""}> ใช้กับห้องแชตที่มีอยู่ของ ${esc(labels[provider] || provider)} ด้วย (ประวัติและความจำยังอยู่ครบ)</label></div><div class="field"><label for="background-model-name">โมเดลสำหรับเลือกรูปภาพและสรุปแชต</label><input id="background-model-name" list="available-models" placeholder="${provider === "xai" ? "เว้นว่าง = grok-4.20-0309-non-reasoning (ประหยัด ไม่มี token คิดในใจ)" : "เว้นว่าง = ใช้โมเดลเดียวกับแชต"}" value="${esc(draft.backgroundModels?.[provider] || "")}" maxlength="160" autocomplete="off"><small>งานเบื้องหลังสั้น ๆ ไม่ต้องใช้โมเดลแพง แนะนำโมเดลแบบ non-reasoning · มีผลทันทีกับทุกห้อง</small></div><div class="inline-actions">${button("test-connection", "ตรวจสอบการเชื่อมต่อ", "secondary", "refresh", 'type="button"')}<span class="pill ${configured ? "green" : ""}">${provider === "ollama" ? "LOCAL ENDPOINT" : configured ? "พบ API KEY ฝั่งเซิร์ฟเวอร์" : "ยังไม่ได้ตั้ง API KEY"}</span></div><div id="connection-result" class="connection-result" role="status"></div><div class="notice">${provider === "ollama" ? "เชื่อมต่อ Ollama ที่ localhost ของเครื่องที่รัน Python · ต้องเปิด Ollama และดาวน์โหลดโมเดลไว้ก่อน" : `ตั้ง ${provider === "xai" ? "XAI_API_KEY" : "OPENAI_API_KEY"} ใน .env แล้วเริ่มเซิร์ฟเวอร์ใหม่ · API key ไม่ถูกส่งมาที่เบราว์เซอร์`}</div>`}<div class="architecture"><span>ตัวละคร + ความจำ</span><b>→</b><span>Backend</span><b>→</b><span>${provider === "demo" ? "Scripted demo" : provider === "ollama" ? "Local Ollama" : "Cloud API"}</span></div></section><section class="panel"><h2>โปรไฟล์ของคุณ</h2><p>ชื่อที่ปรากฏในหน้าบทสนทนา</p><div class="field"><label for="display-name">ชื่อที่แสดง</label><input id="display-name" name="displayName" value="${esc(draft.displayName)}" maxlength="40" required></div></section></div><div><section class="panel"><h2>เนื้อหาและขอบเขต</h2><p>เดโมรองรับบทสนทนาทั่วไป โรแมนซ์ และดราม่า โดยไม่เปิดเนื้อหาทางเพศโจ่งแจ้ง</p><label class="toggle-row"><span><strong>ยืนยันว่าอายุ 18 ปีขึ้นไป</strong><small>เปิดตัวเลือกธีมผู้ใหญ่ในห้องใหม่<br>เป็นการยืนยันด้วยตนเองสำหรับเดโม</small></span><input class="toggle" type="checkbox" id="mature-confirmed" ${draft.matureConfirmed ? "checked" : ""}></label><div class="notice">การเปิดใช้จริงต้องเพิ่มระบบตรวจอายุ การกลั่นกรองเนื้อหา และตรวจนโยบายของโมเดลที่เลือก</div></section><section class="panel"><h2>ข้อมูลและความเป็นส่วนตัว</h2><p>เดโมสำหรับผู้ใช้คนเดียว ข้อมูลแชตและความจำอยู่ใน SQLite บนเครื่องนี้</p><div class="data-line"><span>บทสนทนาที่บันทึก</span><strong>${state.data.rooms.length} ห้อง</strong></div><div class="data-line"><span>ตัวละครที่คุณสร้าง</span><strong>${state.data.characters.filter(c=>c.custom).length} ตัวละคร</strong></div><div class="notice">เมื่อใช้ Cloud เนื้อหาบริบทที่จำเป็นจะถูกส่งไปยังผู้ให้บริการที่เลือก · ไม่มีการสลับจาก Local ไป Cloud อัตโนมัติ</div>${button("export", "ส่งออกข้อมูล JSON", "secondary", "download", 'type="button"')}</section><section class="panel"><h2>About this demo</h2><p>ELYRA · Local-first character stories<br>Python + SQLite · ไม่ต้องติดตั้งแพ็กเกจเพิ่ม<br>ภาพประกอบ SVG ที่เก็บในโปรเจกต์</p></section></div></div><div class="form-actions"><span class="form-error" id="settings-error" role="alert"></span><button type="submit" class="primary">บันทึกการตั้งค่า ${icon("arrow")}</button></div></form></div>`;
}

function render() {
  if (!state.data) return;
  const pages = {discover, chats, characters: charactersPage, gallery: DetailUI.collectionPage, settings: settingsPage, chat: chatPage, character: DetailUI.page};
  $("#app").innerHTML = shell((pages[state.view] || discover)());
  MvpUI.decorate();
  MvpUI.watchSummary();
  if (state.view === "chat") {
    $("#chat-side .tc-side-actions").insertAdjacentHTML("afterend", `<div class="field room-mode-field"><label for="room-mode">โหมดเรื่องราว</label><select id="room-mode" ${state.sending ? "disabled" : ""}><option value="general" ${state.room.mode === "general" ? "selected" : ""}>ทั่วไป</option><option value="mature" ${state.room.mode === "mature" ? "selected" : ""} ${state.data.settings.matureConfirmed ? "" : "disabled"}>ธีมผู้ใหญ่ 18+ · ยืนยันอายุในตั้งค่า</option></select></div>`);
    scrollChat();
  }
}

function scrollChat() { const messages = $("#messages"); if (messages) messages.scrollTop = messages.scrollHeight; }

async function navigate(view, id) {
  if (state.sending) return toast("รอให้ตัวละครตอบเสร็จสักครู่นะ");
  if (view === "chat") {
    state.room = await api(`/api/rooms/${id}`);
    state.view = "chat";
  } else if (view === "character" && id) {
    if (state.view !== "character") state.detailFrom = state.view === "chat" ? "chats" : ["discover", "chats", "characters", "gallery"].includes(state.view) ? state.view : "discover";
    state.detail = {id, slide: 0, tab: "all", chip: "all", introOpen: false};
    state.view = "character";
  } else {
    state.view = ["discover", "chats", "characters", "gallery", "settings"].includes(view) ? view : "discover";
    if (view !== "settings") state.settingsDraft = null;
  }
  history.replaceState(null, "", state.view === "chat" ? `#chat/${state.room.id}` : state.view === "character" ? `#character/${state.detail.id}` : `#${state.view}`);
  render();
  window.scrollTo(0, 0);
}

async function startChat(id, forceNew = false) {
  if (state.sending) return toast("กรุณารอให้บทสนทนาปัจจุบันเสร็จก่อน");
  const existing = state.data.rooms.find(room => room.character_id === id);
  if (existing && !forceNew) return navigate("chat", existing.id);
  const settings = state.data.settings;
  const provider = settings.provider;
  const model = settings.models[provider];
  if (provider !== "demo" && !model) { await navigate("settings"); return toast("เลือกชื่อโมเดลและบันทึกการตั้งค่าก่อนเริ่มคุย", true); }
  const room = await api("/api/rooms", {characterId:id, provider, model, mode:"general"});
  await refresh();
  await navigate("chat", room.id);
}

function openModal(title, body) {
  const modal = $("#modal");
  modal.innerHTML = `<div class="modal-header"><h2>${title}</h2><button class="icon-button" data-action="close-modal" aria-label="ปิดหน้าต่าง">${icon("close")}</button></div><div class="modal-body">${body}</div>`;
  if (!modal.open) modal.showModal();
}

function createCharacterModal() {
  state.selectedArt = "luna";
  openModal("สร้างตัวละครของคุณ", `<form id="character-form"><p class="eyebrow">A NEW STORY STARTS WITH YOU</p><div class="art-picker" role="group" aria-label="เลือกรูปลักษณ์ตัวละคร">${["luna","kael","mira","ren"].map((id,i)=>`<button type="button" class="art-choice ${i===0 ? "active" : ""}" data-action="pick-art" data-art="${id}" aria-label="เลือกรูปลักษณ์ ${id}" aria-pressed="${i===0}"><img src="/assets/${id}.svg" alt=""><span>${["Moonlight","Stargazer","Warm coffee","Old stories"][i]}</span></button>`).join("")}</div><div class="field-row"><div class="field"><label for="char-name">ชื่อตัวละคร *</label><input id="char-name" name="name" maxlength="60" placeholder="ชื่อที่คุณอยากเรียก" required></div><div class="field"><label for="char-age">อายุ (18 ปีขึ้นไป) *</label><input id="char-age" name="age" type="number" min="18" max="1000" value="24" required></div></div><div class="field"><label for="char-subtitle">ประโยคแนะนำสั้น ๆ</label><input id="char-subtitle" name="subtitle" maxlength="100" placeholder="A story waiting to be told"></div><div class="field"><label for="char-description">คำอธิบายตัวละคร *</label><textarea id="char-description" name="description" maxlength="600" placeholder="เขาหรือเธอเป็นใคร และอะไรทำให้คุณอยากรู้จัก?" required></textarea></div><div class="field"><label for="char-personality">บุคลิกและวิธีพูด *</label><textarea id="char-personality" name="personality" maxlength="1500" placeholder="เช่น อบอุ่น ขี้เล่น ชอบถามคำถาม ไม่เร่งรัดความสัมพันธ์" required></textarea></div><div class="field"><label for="char-backstory">ประวัติและโลกของตัวละคร</label><textarea id="char-backstory" name="backstory" maxlength="2000" placeholder="เรื่องราวเบื้องหลัง ความฝัน และสิ่งที่กำลังตามหา"></textarea></div><div class="field"><label for="char-appearance">รูปลักษณ์</label><input id="char-appearance" name="appearance" maxlength="600" placeholder="ทรงผม เสื้อผ้า และรายละเอียดที่เป็นเอกลักษณ์"></div><div class="field"><label for="char-relationship">ความสัมพันธ์เริ่มต้น</label><input id="char-relationship" name="relationship" maxlength="300" placeholder="เช่น เพื่อนบ้านที่เพิ่งย้ายมา"></div><div class="field"><label for="char-greeting">ข้อความเปิดบทสนทนา *</label><textarea id="char-greeting" name="greeting" maxlength="1500" placeholder="*เขาเงยหน้าขึ้นแล้วยิ้มให้* สวัสดี เราเคยเจอกันมาก่อนไหม?" required></textarea><small>ใช้ *ข้อความ* เพื่อบรรยายการกระทำ · ตัวละครจะถูกบันทึกเป็นส่วนตัว</small></div><p class="form-error" id="character-error" role="alert"></p><div class="form-actions">${button("close-modal","ยกเลิก","ghost","",'type="button"')}<button class="primary" type="submit">${icon("sparkle")}สร้างตัวละคร</button></div></form>`);
}

function memoryModal(content = "") {
  openModal("เรื่องที่อยากให้จำ", `<p>ความจำนี้จะใช้เฉพาะในห้องของ ${esc(state.room.character.name)} คุณสามารถลบได้ทุกเมื่อ</p><form id="memory-form"><div class="field"><label for="memory-content">ข้อมูลสำคัญในเรื่องราว</label><textarea id="memory-content" maxlength="500" placeholder="เช่น ฉันชอบดอกทิวลิปสีขาว และอยากให้เรียกว่ามิน" required>${esc(content.slice(0,500))}</textarea><small>สูงสุด 500 ตัวอักษร · ไม่ควรบันทึกรหัสผ่านหรือข้อมูลการเงิน</small></div><p class="form-error" id="memory-error" role="alert"></p><div class="form-actions">${button("close-modal","ยกเลิก","ghost","",'type="button"')}<button class="primary" type="submit">${icon("bookmark")}บันทึกความจำ</button></div></form>`);
}

function readSettingsDraft() {
  const draft = state.settingsDraft || structuredClone(state.data.settings);
  if ($("#display-name")) draft.displayName = $("#display-name").value;
  if ($("#model-name")) draft.models[draft.provider] = $("#model-name").value;
  draft.backgroundModels = {...(draft.backgroundModels || {})};
  if ($("#background-model-name")) draft.backgroundModels[draft.provider] = $("#background-model-name").value;
  if ($("#apply-to-rooms")) draft.applyToRooms = $("#apply-to-rooms").checked;
  if ($("#mature-confirmed")) draft.matureConfirmed = $("#mature-confirmed").checked;
  draft.models.demo = "story-demo";
  state.settingsDraft = draft;
  return draft;
}

async function sendMessage(text) {
  if (state.sending || !text.trim()) return;
  const roomId = state.room.id;
  const input = $("#chat-input");
  const requestId = MvpUI.rememberRequest(roomId, text);
  state.sending = true;
  input.value = "";
  input.disabled = true;
  $("#chat-form button").disabled = true;
  $("#chat-form button").innerHTML = '<span class="spinner"></span>';
  $("#room-provider").disabled = true;
  $(".suggestions")?.remove();
  const userMessage = {role:"user", content:text, created_at:new Date().toISOString(), id:""};
  $("#messages").insertAdjacentHTML("beforeend", messageMarkup(userMessage, state.room.character));
  $("#messages").insertAdjacentHTML("beforeend", messageMarkup({role:"assistant",content:"",provider:state.room.provider,id:""}, state.room.character));
  const responseElement = $("#messages").lastElementChild;
  responseElement.classList.add("streaming");
  let content = "";
  let done = false;
  scrollChat();
  try {
    const response = await fetch(`/api/rooms/${roomId}/chat`, {method:"POST", headers:{"Content-Type":"application/json", "X-Elyra-Token":state.data.token}, body:JSON.stringify({text,requestId})});
    if (!response.ok) { const result = await response.json(); throw new Error(result.error || "ส่งข้อความไม่สำเร็จ"); }
    if (!response.body) throw new Error("เบราว์เซอร์นี้ไม่รองรับ streaming");
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    const processLine = line => {
      if (!line.trim()) return;
      const event = JSON.parse(line);
      if (event.type === "delta") {
        const container = $("#messages");
        const nearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 120;
        content += event.text;
        responseElement.querySelector(".message-text").innerHTML = formatChat(content, state.room.character.name);
        if (nearBottom) scrollChat();
      } else if (event.type === "error") throw new Error(event.message);
      else if (event.type === "done") {
        state.room = event.room;
        MvpUI.finishRequest(roomId);
        done = true;
        for (const milestone of event.unlocked) toast(`✧ ปลดล็อก ${milestone.title} แล้ว! เปิดดูได้ในอัลบั้ม`);
      }
    };
    while (true) {
      const {value, done: streamDone} = await reader.read();
      if (streamDone) break;
      buffer += decoder.decode(value, {stream:true});
      const lines = buffer.split("\n");
      buffer = lines.pop();
      for (const line of lines) processLine(line);
    }
    buffer += decoder.decode();
    if (buffer.trim()) processLine(buffer);
    if (!done) throw new Error("การเชื่อมต่อขาดก่อนจบคำตอบ กรุณาลองอีกครั้ง");
    await refresh();
  } catch (error) {
    toast(error.message, true);
    // Server commits complete pairs only. Reconcile before showing a retry.
    try { state.room = await api(`/api/rooms/${roomId}`); } catch { /* Keep last known room. */ }
    state.retryDraft = text;
  } finally {
    state.sending = false;
    render();
    if (state.retryDraft && $("#chat-input")) { $("#chat-input").value = state.retryDraft; state.retryDraft = ""; }
    $("#chat-input")?.focus();
  }
}

async function handleAction(element) {
  const action = element.dataset.action;
  if (state.sending && !["toggle-info","close-sidebar","menu","close-modal"].includes(action)) return toast("รอให้ตัวละครตอบเสร็จสักครู่นะ");
  if (await DetailUI.action(element)) return;
  if (await MvpUI.action(element)) return;
  if (action === "chat-peek") { state.chatPeek = !state.chatPeek; $(".tc-chat").classList.toggle("peek", state.chatPeek); element.setAttribute("aria-pressed", state.chatPeek); return; }
  if (action === "insert-situation") {
    const input = $("#chat-input");
    const start = input.selectionStart ?? input.value.length;
    const end = input.selectionEnd ?? start;
    const selected = input.value.slice(start, end);
    input.value = `${input.value.slice(0, start)}*${selected}*${input.value.slice(end)}`;
    input.focus();
    input.setSelectionRange(start + 1, start + 1 + selected.length);
    input.dispatchEvent(new Event("input", {bubbles: true}));
    return;
  }
  if (action === "navigate") return navigate(element.dataset.view);
  if (action === "open-room") return navigate("chat", element.dataset.id);
  if (action === "start-chat") return startChat(element.dataset.id);
  if (action === "create-character") return createCharacterModal();
  if (action === "close-modal") return $("#modal").close();
  if (action === "menu") { $(".sidebar").classList.toggle("open"); $(".mobile-scrim").classList.toggle("open"); return; }
  if (action === "close-sidebar") { $(".sidebar").classList.remove("open"); $(".mobile-scrim").classList.remove("open"); return; }
  if (action === "toggle-info") return $("#chat-side").classList.toggle("open");
  if (action === "filter") { state.filter = element.dataset.filter; render(); return; }
  if (action === "gallery-filter") { state.galleryFilter = element.dataset.filter; render(); return; }
  if (action === "favorite") {
    const id = element.dataset.id;
    state.favorites.has(id) ? state.favorites.delete(id) : state.favorites.add(id);
    try { localStorage.setItem("elyra-favorites", JSON.stringify([...state.favorites])); } catch { /* Favorite remains for this session. */ }
    render(); return;
  }
  if (action === "pick-art") {
    state.selectedArt = element.dataset.art;
    document.querySelectorAll(".art-choice").forEach(item => { const active = item === element; item.classList.toggle("active", active); item.setAttribute("aria-pressed", active); });
    return;
  }
  if (action === "suggest") return sendMessage(element.dataset.text);
  if (action === "add-memory") return memoryModal();
  if (action === "remember-message") {
    const message = state.room.messages.find(item => item.id === element.dataset.id);
    return memoryModal(message?.content || "");
  }
  if (action === "forget") { state.room = await api(`/api/rooms/${state.room.id}/forget`, {memoryId:element.dataset.id}); render(); toast("ลบความจำนี้แล้ว"); return; }
  if (action === "new-chapter") {
    return openModal("เริ่มเรื่องราวบทใหม่?", `<p>เปิดห้องใหม่กับ ${esc(state.room.character.name)} โดยเริ่มความจำและความคืบหน้าใหม่ บทสนทนาเดิมยังเปิดอ่านได้ตามปกติ</p><div class="form-actions">${button("close-modal","ยกเลิก","ghost","")}${button("confirm-new-chapter","เริ่มบทใหม่","primary","sparkle")}</div>`);
  }
  if (action === "confirm-new-chapter") { $("#modal").close(); return startChat(state.room.character.id, true); }
  if (action === "delete-room") return openModal("ลบบทสนทนานี้?", `<p>ข้อความ ความจำ และประวัติปลดล็อกของห้องนี้จะถูกลบออกจากเครื่อง การกระทำนี้ย้อนกลับไม่ได้</p><div class="form-actions">${button("close-modal","เก็บไว้ก่อน","ghost","")}${button("confirm-delete-room","ลบบทสนทนา","danger","trash")}</div>`);
  if (action === "confirm-delete-room") {
    await api(`/api/rooms/${state.room.id}/delete`, {});
    $("#modal").close(); state.room = null; await refresh(); await navigate("chats"); toast("ลบบทสนทนาและความจำแล้ว"); return;
  }
  if (action === "choose-provider") { readSettingsDraft().provider = element.dataset.provider; render(); return; }
  if (action === "test-connection") {
    readSettingsDraft();
    const provider = state.settingsDraft.provider;
    const result = $("#connection-result");
    result.classList.remove("error"); result.textContent = "กำลังตรวจสอบและโหลดรายชื่อโมเดล…"; element.disabled = true;
    try {
      const data = await api(`/api/models?provider=${provider}`);
      state.modelLists[provider] = data.models;
      $("#available-models").innerHTML = data.models.map(model=>`<option value="${esc(model)}"></option>`).join("");
      result.textContent = data.models.length ? `เชื่อมต่อสำเร็จ · พบ ${data.models.length} โมเดล เลือกจากช่องชื่อโมเดลด้านบน` : "เชื่อมต่อสำเร็จ แต่ยังไม่มีโมเดล กรุณาดาวน์โหลดโมเดลใน Ollama ก่อน";
    } catch (error) { result.textContent = error.message; result.classList.add("error"); }
    finally { element.disabled = false; }
    return;
  }
  if (action === "export") {
    const data = await api("/api/export");
    const url = URL.createObjectURL(new Blob([JSON.stringify(data,null,2)], {type:"application/json"}));
    const link = document.createElement("a"); link.href = url; link.download = `elyra-stories-${new Date().toISOString().slice(0,10)}.json`; link.click();
    setTimeout(()=>URL.revokeObjectURL(url),1000); toast("ส่งออกข้อมูลแล้ว"); return;
  }
  if (action === "locked-moment") return toast("คุยกับตัวละครให้ถึงจำนวนรอบที่ระบุ เพื่อปลดล็อกภาพนี้");
  if (action === "view-moment") {
    const character = state.data.characters.find(item=>item.id === element.dataset.character);
    const milestone = state.data.milestones.find(item=>item.id === element.dataset.milestone);
    return openModal(`${milestone.title} · ${esc(character.name)}`, `<img class="modal-scene" src="/assets/${character.art}-${milestone.scene}.svg" alt="${esc(milestone.title)}"><p>${milestone.description} — ความทรงจำกับ ${esc(character.name)}</p><div class="form-actions">${button("close-modal","เก็บช่วงเวลานี้ไว้","primary","heart")}</div>`);
  }
}

document.addEventListener("click", event => {
  const button = event.target.closest("[data-action]");
  if (button) { if (button.disabled) return; event.preventDefault(); Promise.resolve(handleAction(button)).catch(error=>toast(error.message,true)); }
  if (event.target.closest(".search") && window.innerWidth <= 700) { $(".search").classList.add("expanded"); $("#global-search").focus(); }
});

document.addEventListener("submit", async event => {
  event.preventDefault();
  const form = event.target;
  const submit = form.querySelector('[type="submit"]');
  if (submit?.disabled) return;
  if (form.id === "chat-form") return sendMessage($("#chat-input").value).catch(error=>toast(error.message,true));
  if (submit) submit.disabled = true;
  const errorElement = form.querySelector(".form-error");
  if (errorElement) errorElement.textContent = "";
  try {
    if (form.id === "character-form") {
      await MvpUI.saveCharacter(form);
    } else if (form.id === "image-settings-form") {
      await MvpUI.saveImageSettings(form);
    } else if (form.id === "memory-form") {
      state.room = await api(`/api/rooms/${state.room.id}/memory`, {content:$("#memory-content").value}); $("#modal").close(); render(); toast("บันทึกความจำสำหรับห้องนี้แล้ว");
    } else if (form.id === "notes-form") {
      state.room = await api(`/api/rooms/${state.room.id}/notes`, {content:$("#story-notes-input").value});
      $("#modal").close(); render(); toast("บันทึกสรุปเรื่องราวแล้ว");
    } else if (form.id === "settings-form") {
      const draft = readSettingsDraft();
      if (draft.provider !== "demo" && !draft.models[draft.provider]?.trim()) throw new Error("กรุณาเลือกหรือระบุชื่อโมเดลก่อนบันทึก");
      const saved = await api("/api/settings", draft); await refresh(); state.settingsDraft = null; render();
      toast(saved.roomsUpdated ? `บันทึกแล้ว · เปลี่ยนโมเดลแชตให้ห้องเดิม ${saved.roomsUpdated} ห้อง` : "บันทึกแล้ว โมเดลแชตใช้กับห้องที่สร้างต่อจากนี้ · โมเดลเลือกรูปภาพมีผลทันที");
    }
  } catch (error) { if (errorElement) errorElement.textContent = error.message; else toast(error.message,true); }
  finally { if (submit?.isConnected) submit.disabled = false; }
});

document.addEventListener("change", async event => {
  if (event.target.matches("[data-upload-target]")) {
    try { await MvpUI.upload(event.target); }
    catch(error) { if ($("#character-error")) $("#character-error").textContent=error.message; else toast(error.message,true); }
    return;
  }
  if (!["room-provider", "room-mode"].includes(event.target.id)) return;
  if (state.sending) { render(); return; }
  const provider = $("#room-provider").value;
  const mode = $("#room-mode")?.value || state.room.mode;
  const model = provider === state.room.provider ? state.room.model : state.data.settings.models[provider];
  if (provider !== "demo" && (!model || !state.data.providers[provider].configured)) {
    event.target.value = state.room.provider;
    toast("ตั้งค่า API และชื่อโมเดลในหน้าตั้งค่าก่อนเปลี่ยนผู้ให้บริการ",true); return;
  }
  try { state.room = await api(`/api/rooms/${state.room.id}/configure`, {provider,model,mode}); await refresh(); render(); toast("อัปเดตห้องแล้ว ประวัติและความจำยังอยู่ในห้องนี้"); }
  catch(error) { toast(error.message,true); render(); }
});

let searchTimer;
document.addEventListener("input", event => {
  if (event.target.id === "chat-input" && state.room) {
    try { sessionStorage.setItem(`elyra-draft-${state.room.id}`,event.target.value); } catch { /* Storage optional. */ }
    return;
  }
  if (event.target.id !== "global-search") return;
  state.search = event.target.value;
  clearTimeout(searchTimer);
  searchTimer = setTimeout(async()=>{
    if (state.sending) return;
    if (!["discover","characters"].includes(state.view)) state.view = "discover";
    const position = event.target.selectionStart;
    render();
    const input = $("#global-search");
    if (window.innerWidth <= 700) $(".search").classList.add("expanded");
    input.focus(); input.setSelectionRange(position, position);
  },180);
});

document.addEventListener("keydown", event => {
  if (event.target.id === "chat-input" && event.key === "Enter" && !event.shiftKey && !event.isComposing) { event.preventDefault(); $("#chat-form").requestSubmit(); }
  if (event.key === "/" && !["INPUT","TEXTAREA","SELECT"].includes(document.activeElement.tagName) && !$("#modal").open) { event.preventDefault(); $(".search").classList.add("expanded"); $("#global-search").focus(); }
  if (event.key === "Escape") { $(".search")?.classList.remove("expanded"); $(".sidebar")?.classList.remove("open"); $(".mobile-scrim")?.classList.remove("open"); $("#chat-side")?.classList.remove("open"); }
});
$("#modal").addEventListener("click", event => { if (event.target === $("#modal")) { const rect = event.target.getBoundingClientRect(); if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) event.target.close(); } });
window.addEventListener("hashchange", () => { const [view,id] = location.hash.slice(1).split("/"); navigate(view,id).catch(error=>toast(error.message,true)); });

(async()=>{
  try { await refresh(); const [view,id] = location.hash.slice(1).split("/"); await navigate(view || "discover",id); }
  catch(error) { $("#app").innerHTML = `<div class="boot"><span class="brand-mark">✧</span><h1>ELYRA</h1><p>${esc(error.message)}</p><p>เปิดผ่าน python app.py แล้วเข้า http://localhost:3000</p></div>`; }
})();
