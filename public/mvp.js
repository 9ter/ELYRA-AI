"use strict";

// Character authoring and story tools. Uses the shared API/render helpers in app.js.
const MvpUI = (() => {
  let editor = null;
  let summaryTimer = null;
  let summaryWatchVersion = 0;

  function summaryMarkup(room) {
    const text = room.summary || "";
    const turns = Math.max(0, Math.floor(((room.summary_count || 0) - 1) / 2));
    const status = room.summary_state === "updating" ? "AI กำลังอัปเดตสรุป… คุยต่อได้เลย" :
      room.summary_state === "error" ? "ยังอัปเดตสรุปไม่สำเร็จ ระบบจะลองใหม่หลังข้อความถัดไป" :
      text ? `สรุปอัตโนมัติแล้ว ${turns} รอบ · บทสนทนาล่าสุดยังเก็บไว้ครบ` :
      room.provider === "demo" ? "โหมดจำลองยังไม่เรียก AI เพื่อสรุปเรื่องราว" : "AI จะสรุปให้อัตโนมัติเมื่อบทสนทนายาวขึ้น";
    return `<div class="side-heading">สรุปเรื่องราว<span class="summary-auto-badge">AUTO</span></div>
      ${text ? `<p class="side-empty story-notes-preview auto-summary-text">${esc(text)}</p>` : ""}
      <p class="progress-caption auto-summary-status" role="status">${esc(status)}</p>`;
  }

  function watchSummary() {
    const version = ++summaryWatchVersion;
    clearTimeout(summaryTimer);
    if (state.view !== "chat" || !state.room) return;
    const roomId = state.room.id;
    async function poll() {
      if (version !== summaryWatchVersion) return;
      try {
        if (!state.sending && !document.hidden) {
          const result = await api(`/api/rooms/${roomId}/summary`);
          if (version !== summaryWatchVersion || state.view !== "chat" || state.room?.id !== roomId) return;
          Object.assign(state.room, result);
          const panel = $(".auto-story-summary");
          const markup = summaryMarkup(state.room);
          if (panel && panel.summaryMarkup !== markup) {
            panel.innerHTML = markup;
            panel.summaryMarkup = markup;
          }
        }
      } catch { /* Preserve the last summary during temporary connection failures. */ }
      finally {
        if (version === summaryWatchVersion) summaryTimer = setTimeout(poll, 3000);
      }
    }
    summaryTimer = setTimeout(poll, 300);
  }
  const imageFields = new Set(["portrait", "first-light", "little-rituals", "under-the-stars"]);
  const field = (id, label, maximum, options = {}) => `<div class="field"><label for="char-${id}">${label}${options.required ? " *" : ""}</label>${options.area ? `<textarea id="char-${id}" name="${id}" maxlength="${maximum}" ${options.required ? "required" : ""}></textarea>` : `<input id="char-${id}" name="${id}" maxlength="${maximum}" ${options.required ? "required" : ""}>`}${options.help ? `<small>${options.help}</small>` : ""}</div>`;
  const imageUrl = id => /^[a-f0-9]{64}$/.test(id || "") ? `/media/${id}` : "";
  const sceneTiers = [["common", "ทั่วไป"], ["rare", "หายาก"], ["legend", "ตำนาน"]];

  function readScenes() {
    // Pull the latest typed values from the DOM into the editor model before re-rendering or saving.
    document.querySelectorAll(".scene-row").forEach(row => {
      const scene = editor.scenes[Number(row.dataset.index)];
      if (!scene) return;
      scene.title = row.querySelector("[data-scene-field=title]").value;
      scene.description = row.querySelector("[data-scene-field=description]").value;
      scene.tier = row.querySelector("[data-scene-field=tier]").value;
      scene.min_turns = Number(row.querySelector("[data-scene-field=min_turns]").value) || 0;
      scene.prompt = row.querySelector("[data-scene-field=prompt]").value;
      scene.negative = row.querySelector("[data-scene-field=negative]").value;
    });
    return editor.scenes;
  }

  function readLoras() {
    document.querySelectorAll(".lora-row").forEach(row => {
      const lora = editor.loras[Number(row.dataset.index)];
      if (!lora) return;
      lora.name = row.querySelector("[data-lora-field=name]").value.trim();
      lora.weight = Number(row.querySelector("[data-lora-field=weight]").value);
      lora.trigger = row.querySelector("[data-lora-field=trigger]").value;
    });
    return editor.loras;
  }

  function renderLoras() {
    const list = $("#lora-editor");
    if (!list) return;
    list.innerHTML = editor.loras.length ? editor.loras.map((lora, index) => `<div class="lora-row" data-index="${index}">
      <label>ชื่อ LoRA<input data-lora-field="name" list="lora-options" maxlength="120" placeholder="เลือกหรือพิมพ์ชื่อไฟล์ LoRA" value="${esc(lora.name)}"></label>
      <label>น้ำหนัก<input data-lora-field="weight" type="number" min="-2" max="2" step="0.05" value="${esc(lora.weight)}"></label>
      <label>คำเรียก (trigger words)<input data-lora-field="trigger" maxlength="200" placeholder="เช่น yoonseoah" value="${esc(lora.trigger || "")}"></label>
      <button type="button" class="ghost" data-action="remove-lora" data-index="${index}" aria-label="ลบ LoRA">${icon("trash")}</button></div>`).join("")
      : `<p class="scene-empty">ยังไม่ได้ผูก LoRA · ภาพจะใช้แค่แท็กรูปลักษณ์ด้านบน</p>`;
  }

  async function fillLoraOptions() {
    // Offer the LoRA files Forge knows about; typing a name by hand still works if Forge is offline.
    try { if (!imageOptions?.loras) imageOptions = await api("/api/images/options"); } catch { return; }
    const options = $("#lora-options");
    if (options) options.innerHTML = (imageOptions.loras || []).map(name => `<option value="${esc(name)}"></option>`).join("");
    const note = $("#lora-available");
    if (note) note.textContent = imageOptions.loras?.length ? `พบ LoRA ใน Forge ${imageOptions.loras.length} ไฟล์` : "ยังไม่พบไฟล์ LoRA ใน Forge (วางไฟล์ในโฟลเดอร์ Lora ของ Stability Matrix แล้วเปิดหน้านี้ใหม่)";
  }

  function renderScenes() {
    const list = $("#scene-editor");
    if (!list) return;
    list.innerHTML = editor.scenes.length ? editor.scenes.map((scene, index) => `<div class="scene-row" data-index="${index}">
      <div class="scene-image">${imageUrl(scene.media_id) ? `<img id="scene-preview-${index}" class="zoomable" data-action="zoom-image" src="${imageUrl(scene.media_id)}" alt="${esc(scene.title || scene.description)}" title="กดเพื่อดูภาพเต็ม">` : `<span id="scene-preview-${index}">${icon("image")}</span>`}<label class="secondary upload-label">${icon("image")}เลือกรูป<input type="file" accept="image/png,image/jpeg,image/webp" data-upload-target="scene:${index}" class="sr-only"></label></div>
      <div class="scene-fields"><label>ป้ายกำกับ (ชื่อสั้น ๆ แสดงในคอลเลกชัน)<input data-scene-field="title" maxlength="40" placeholder="เช่น ยาขม" value="${esc(scene.title || "")}"></label><label>คำอธิบายฉาก (ให้ AI ใช้เลือกภาพ)<textarea data-scene-field="description" maxlength="300" placeholder="เช่น ซออานอนป่วยบนเตียง หน้าแดงจากไข้ ห่มผ้า กลางคืน">${esc(scene.description)}</textarea></label>
        <label>Prompt สร้างภาพ (ภาษาอังกฤษ ไม่บังคับ)<textarea data-scene-field="prompt" maxlength="1000" placeholder="e.g. lying in bed, under blanket, flushed, fever, bedroom, night">${esc(scene.prompt || "")}</textarea></label>
        <label>Negative prompt ของฉากนี้ (ไม่บังคับ)<textarea data-scene-field="negative" class="negative-input" maxlength="1000" placeholder="สิ่งที่ไม่อยากให้มีในภาพนี้ เช่น extra people, glasses, outdoors">${esc(scene.negative || "")}</textarea></label>
        <button type="button" class="secondary scene-generate" data-action="generate-scene" data-index="${index}">${icon("sparkle")}สร้างภาพด้วย AI (Stable Diffusion ในเครื่อง)</button>
        <div class="scene-meta"><label>ระดับ<select data-scene-field="tier">${sceneTiers.map(([id, label]) => `<option value="${id}" ${scene.tier === id ? "selected" : ""}>${label}</option>`).join("")}</select></label><label>คุยอย่างน้อย (รอบ)<input data-scene-field="min_turns" type="number" min="0" max="500" value="${scene.min_turns}"></label><button type="button" class="ghost" data-action="remove-scene" data-index="${index}">${icon("trash")}ลบ</button></div></div></div>`).join("")
      : `<p class="scene-empty">ยังไม่มีภาพตามสถานการณ์</p>`;
  }

  function pending(roomId) {
    try { return JSON.parse(sessionStorage.getItem(`elyra-pending-${roomId}`) || "null"); } catch { return null; }
  }

  function rememberRequest(roomId, text) {
    const existing = pending(roomId);
    const request = existing?.text === text ? existing : {id: newId(), text};
    try { sessionStorage.setItem(`elyra-pending-${roomId}`, JSON.stringify(request)); sessionStorage.removeItem(`elyra-draft-${roomId}`); } catch { /* Request still deduplicates within this call. */ }
    return request.id;
  }

  function finishRequest(roomId) {
    try { sessionStorage.removeItem(`elyra-pending-${roomId}`); sessionStorage.removeItem(`elyra-draft-${roomId}`); } catch { /* Storage is optional. */ }
  }

  function draft(roomId) {
    try { return sessionStorage.getItem(`elyra-draft-${roomId}`) || pending(roomId)?.text || ""; } catch { return ""; }
  }

  let imageOptions = null;  // cached Forge choices + saved settings; refetched by the reload button

  const numberField = (key, label, attrs, value) => `<div class="field"><label for="img-${key}">${label}</label><input id="img-${key}" name="${key}" type="number" ${attrs} value="${esc(value)}" required></div>`;
  const selectField = (key, label, choices, value, blank = "") => {
    const list = choices.includes(value) || !value ? choices : [value, ...choices];
    return `<div class="field"><label for="img-${key}">${label}</label><select id="img-${key}" name="${key}">${blank ? `<option value="">${esc(blank)}</option>` : ""}${list.map(item => `<option value="${esc(item)}" ${item === value ? "selected" : ""}>${esc(item)}</option>`).join("")}</select></div>`;
  };

  function renderImageSettings() {
    const body = $("#image-settings-body");
    if (!body || !imageOptions) return;
    if (imageOptions.error) {
      body.innerHTML = `<div class="notice">${esc(imageOptions.error)}</div><button type="button" class="secondary" data-action="reload-image-options">${icon("refresh")}ลองเชื่อมต่ออีกครั้ง</button>`;
      return;
    }
    const s = imageOptions.settings;
    const current = imageOptions.current_checkpoint ? `ใช้โมเดลที่ Forge โหลดอยู่ (${imageOptions.current_checkpoint})` : "ใช้โมเดลที่ Forge โหลดอยู่";
    body.innerHTML = `<form id="image-settings-form">
      ${selectField("checkpoint", "โมเดล (Checkpoint)", imageOptions.checkpoints, s.checkpoint, current)}
      <div class="field-row">${selectField("sampler_name", "Sampling method", imageOptions.samplers, s.sampler_name)}${selectField("scheduler", "Schedule type", imageOptions.schedulers, s.scheduler)}</div>
      <div class="field-row">${numberField("steps", "Sampling steps", 'min="1" max="150" step="1"', s.steps)}${numberField("cfg_scale", "CFG scale", 'min="1" max="30" step="0.5"', s.cfg_scale)}</div>
      <div class="field-row">${numberField("width", "Width (หาร 8 ลงตัว)", 'min="256" max="2048" step="8"', s.width)}${numberField("height", "Height (หาร 8 ลงตัว)", 'min="256" max="2048" step="8"', s.height)}</div>
      <label class="toggle-row"><span><strong>Hires. fix</strong><small>ขยายภาพและเติมรายละเอียดรอบสอง ภาพคมขึ้นแต่ใช้เวลานานขึ้น</small></span><input class="toggle" type="checkbox" name="enable_hr" ${s.enable_hr ? "checked" : ""}></label>
      <div class="hires-fields">
        <div class="field-row">${selectField("hr_upscaler", "Upscaler", imageOptions.upscalers, s.hr_upscaler)}${numberField("hr_scale", "Upscale by", 'min="1" max="4" step="0.05"', s.hr_scale)}</div>
        <div class="field-row">${numberField("hr_second_pass_steps", "Hires steps", 'min="0" max="150" step="1"', s.hr_second_pass_steps)}${numberField("denoising_strength", "Denoising strength", 'min="0" max="1" step="0.05"', s.denoising_strength)}</div>
        ${numberField("hr_cfg", "Hires CFG scale", 'min="1" max="30" step="0.5"', s.hr_cfg)}
      </div>
      <p class="image-size-note" id="image-size-note"></p>
      <p class="form-error" role="alert"></p>
      <div class="form-actions"><button type="button" class="ghost" data-action="reset-image-settings">คืนค่าเริ่มต้น</button><button type="button" class="secondary" data-action="reload-image-options">${icon("refresh")}โหลดรายการจาก Forge ใหม่</button><button type="submit" class="primary">บันทึกการตั้งค่าสร้างภาพ</button></div>
    </form>`;
    updateImageSizeNote();
  }

  function readImageSettings(form) {
    const data = {};
    for (const element of form.elements) {
      if (!element.name) continue;
      data[element.name] = element.type === "checkbox" ? element.checked : element.type === "number" ? Number(element.value) : element.value;
    }
    return data;
  }

  function updateImageSizeNote() {
    const form = $("#image-settings-form");
    const note = $("#image-size-note");
    if (!form || !note) return;
    const s = readImageSettings(form);
    const scale = s.enable_hr ? s.hr_scale : 1;
    form.querySelector(".hires-fields").classList.toggle("disabled", !s.enable_hr);
    note.textContent = `ขนาดภาพสุดท้าย ${Math.round(s.width * scale)} × ${Math.round(s.height * scale)} px`;
  }

  async function loadImageOptions() {
    imageOptions = null;
    if ($("#image-settings-body")) $("#image-settings-body").innerHTML = '<p class="side-empty">กำลังโหลดรายการจาก Forge…</p>';
    try { imageOptions = await api("/api/images/options"); }
    catch (error) { imageOptions = {error: error.message}; }
    renderImageSettings();
  }

  async function saveImageSettings(form) {
    const saved = await api("/api/images/settings", readImageSettings(form));
    imageOptions = {...imageOptions, settings: saved};
    renderImageSettings();
    toast("บันทึกการตั้งค่าสร้างภาพแล้ว ใช้กับภาพถัดไปทันที");
  }

  function decorate() {
    if (state.view === "settings" && $("#settings-form") && !$("#image-settings-panel")) {
      $("#settings-form").insertAdjacentHTML("afterend", `<section class="panel image-settings" id="image-settings-panel"><h2>สร้างภาพ (Stable Diffusion ในเครื่อง)</h2><p>เลือกโมเดลและค่าที่ใช้กับปุ่ม "สร้างภาพด้วย AI" ในหน้าแก้ไขตัวละคร รายการดึงจาก Forge ที่เปิดอยู่ (ต้องเปิดด้วย --api)</p><div id="image-settings-body"></div></section>`);
      if (imageOptions) renderImageSettings(); else loadImageOptions();
    }
    document.querySelectorAll(".character-card").forEach(card => {
      const start = card.querySelector('[data-action="start-chat"]');
      const character = state.data.characters.find(item => item.id === start?.dataset.id);
      if (!character) return;
      const actions = document.createElement("div");
      actions.className = "character-tools";
      actions.innerHTML = `<button data-action="character-details" data-id="${character.id}">${icon("book")}รายละเอียด</button>
        ${character.custom ? `<button data-action="edit-character" data-id="${character.id}" aria-label="แก้ไข ${esc(character.name)}">${icon("settings")}แก้ไข</button>` : ""}
        <button data-action="clone-character" data-id="${character.id}" aria-label="ทำสำเนา ${esc(character.name)}">${icon("plus")}ทำสำเนา</button>
        ${character.custom ? `<button data-action="${character.archived ? "restore-character" : "archive-character"}" data-id="${character.id}">${icon(character.archived ? "refresh" : "book")}${character.archived ? "นำกลับ" : "เก็บเข้าคลัง"}</button>` : ""}`;
      card.querySelector(".card-body").append(actions);
      if (character.archived) { start.disabled = true; start.textContent = "อยู่ในคลัง"; }
    });
    if (state.view === "characters") {
      const count = state.data.characters.filter(item => item.custom && item.archived).length;
      $(".page-heading").insertAdjacentHTML("afterend", `<div class="filters character-library"><button class="filter ${state.showArchived ? "" : "active"}" data-action="show-active-characters">ตัวละครที่ใช้งาน</button><button class="filter ${state.showArchived ? "active" : ""}" data-action="show-archived-characters">คลังตัวละคร (${count})</button></div>`);
    }
    if (state.view === "chat" && state.room) {
      const room = state.room;
      const character = room.character;
      const current = state.data.characters.find(item => item.id === character.id);
      const side = $("#chat-side");
      side.querySelector(".side-description").insertAdjacentHTML("afterend", `
        ${character.tips ? `<div class="character-tips"><strong>เคล็ดลับเริ่มเรื่อง</strong><p>${esc(character.tips)}</p></div>` : ""}
        ${current && (current.version || 1) > (character.version || 1) ? `<div class="notice">มีข้อมูลตัวละครฉบับใหม่แล้ว เริ่มบทใหม่เพื่อใช้ข้อมูลล่าสุด</div>` : ""}
        <section class="auto-story-summary" aria-label="สรุปเรื่องราวอัตโนมัติ">${summaryMarkup(room)}</section>
        ${room.notes ? `<details class="legacy-story-notes"><summary>บันทึกเดิมของคุณ</summary><p class="side-empty story-notes-preview">${esc(room.notes)}</p><button class="ghost" data-action="story-notes">แก้ไขบันทึกส่วนตัว</button></details>` : ""}`);
      if (!state.sending && $("#chat-input")) $("#chat-input").value = draft(room.id);
      $(".composer-note").insertAdjacentHTML("afterend", `<p class="local-data-note">${room.parent_room_id ? "เส้นเรื่องแยก · " : ""}ความจำและสรุปเรื่องราวใช้เฉพาะห้องนี้</p>`);
      document.querySelectorAll(".message.assistant[data-message-id]").forEach(message => {
        if (!message.dataset.messageId) return;
        message.querySelector(".message-tools").insertAdjacentHTML("beforeend", `<button data-action="branch-story" data-id="${message.dataset.messageId}">${icon("book")}แตกเส้นเรื่องจากตรงนี้</button>`);
      });
      let turns = 0;
      for (const message of room.messages) {
        if (message.role === "user") turns++;
        if (message.role !== "assistant" || !turns) continue;
        const milestone = state.data.milestones.find(item => item.threshold === turns && room.unlocks.includes(item.id));
        if (!milestone) continue;
        const element = document.querySelector(`.message[data-message-id="${message.id}"]`);
        element?.insertAdjacentHTML("afterend", `<button class="story-moment" data-action="view-moment" data-room="${room.id}" data-character="${character.id}" data-milestone="${milestone.id}"><img src="${momentArt(character,milestone)}" alt="${milestone.title}"><span>${icon("sparkle")}ปลดล็อกความทรงจำ · ${milestone.title}<small>เก็บในอัลบั้มแล้ว · กดเพื่อดูภาพ</small></span></button>`);
      }
    }
  }

  function openEditor(character = null, duplicate = false) {
    const source = character ? structuredClone(character) : {};
    editor = {id: duplicate ? null : character?.id || null, expectedVersion: character?.version || 1,
      portrait_id: source.portrait_id || "", gallery: source.gallery || {}, scenes: source.scenes || [],
      loras: source.image_loras || [], uploading: false};
    state.selectedArt = source.art || "luna";
    const title = editor.id ? `แก้ไข ${esc(character.name)}` : duplicate ? "ทำสำเนาตัวละคร" : "สร้างตัวละครของคุณ";
    openModal(title, `<form id="character-form">
      <p class="eyebrow">YOUR CHARACTER, YOUR STORY</p>
      <div class="portrait-upload"><img id="character-image-preview" class="zoomable" data-action="zoom-image" src="${art(source)}" alt="ภาพตัวละครที่เลือก" title="กดเพื่อดูภาพเต็ม"><div><strong>รูปโปรไฟล์ตัวละคร</strong><p>อัปโหลดภาพของคุณ หรือเลือกรูปลักษณ์ด้านล่าง</p><label class="secondary upload-label">${icon("image")}เลือกรูป<input type="file" accept="image/png,image/jpeg,image/webp" data-upload-target="portrait" class="sr-only"></label><small id="portrait-upload-status">ภาพจะย่อให้ด้านยาวไม่เกิน 1,200 px</small></div></div>
      <div class="art-picker" role="group" aria-label="รูปลักษณ์สำเร็จรูป">${["luna","kael","mira","ren"].map(id=>`<button type="button" class="art-choice ${state.selectedArt === id && !editor.portrait_id ? "active" : ""}" data-action="pick-art" data-art="${id}" aria-label="เลือกรูปลักษณ์ ${id}"><img src="/assets/${id}.svg" alt=""><span>${id[0].toUpperCase()+id.slice(1)}</span></button>`).join("")}</div>
      <div class="field-row">${field("name","ชื่อตัวละคร",60,{required:true})}<div class="field"><label for="char-age">อายุ (18 ปีขึ้นไป) *</label><input id="char-age" name="age" type="number" min="18" max="1000" value="24" required></div></div>
      ${field("subtitle","ประโยคแนะนำสั้น ๆ",100)}
      ${field("description","คำอธิบายตัวละคร",600,{area:true,required:true})}
      ${field("personality","บุคลิกภาพ",3000,{area:true,required:true,help:"นิสัยหลัก แรงจูงใจ ด้านที่ซ่อนอยู่"})}
      <details class="persona-details" ${["speech_style","example_dialogue","likes","dislikes","reactions","relationship_arc"].some(key=>source[key]) ? "open" : ""}><summary>บุคลิกแบบละเอียด (ไม่บังคับ)</summary>
      ${field("speech_style","วิธีพูดและคำติดปาก",1000,{area:true,help:"สรรพนามที่ใช้ คำลงท้าย น้ำเสียง ความยาวประโยค"})}
      ${field("example_dialogue","ตัวอย่างบทสนทนา",3000,{area:true,help:"2–4 คู่ถามตอบที่แสดงน้ำเสียงจริง AI ใช้เป็นแนวทาง ไม่ลอกคำต่อคำ เช่น\nผู้ใช้: ...\nตัวละคร: ..."})}
      <div class="field-row">${field("likes","สิ่งที่ชอบ",600,{area:true})}${field("dislikes","สิ่งที่ไม่ชอบ",600,{area:true})}</div>
      ${field("reactions","ปฏิกิริยาต่อสถานการณ์",1500,{area:true,help:"เช่น ถ้าถูกแกล้งกลับ… / ถ้าผู้ใช้เศร้า… / ถ้าถูกชม…"})}
      ${field("relationship_arc","พัฒนาการความสัมพันธ์",1500,{area:true,help:"ความสัมพันธ์ค่อย ๆ เปลี่ยนอย่างไรเมื่อสนิทกันมากขึ้น"})}
      </details>
      ${field("backstory","ประวัติและโลกของตัวละคร",3000,{area:true})}
      ${field("appearance","รูปลักษณ์",600)}
      ${field("image_prompt","รูปลักษณ์สำหรับสร้างภาพ (ภาษาอังกฤษ)",600,{help:"แท็กที่ใช้กับทุกภาพของตัวละคร ให้หน้าตาคงที่ เช่น long straight silver hair, purple eyes, heart pendant necklace"})}
      ${field("image_negative","Negative prompt ของตัวละคร (ภาษาอังกฤษ)",1000,{area:true,help:"สิ่งที่ไม่อยากให้มีในทุกภาพของตัวละครนี้ เช่น short hair, glasses, tattoo · ระบบใส่ค่าพื้นฐานและคำกันภาพดูเป็นเด็กให้อยู่แล้ว"})}
      <div class="lora-section"><strong>LoRA ของตัวละคร</strong><p>ผูก LoRA เพื่อให้หน้าตาเหมือนเดิมทุกภาพ ระบบจะใส่ให้อัตโนมัติทุกครั้งที่กด "สร้างภาพด้วย AI" ของตัวละครนี้ <small id="lora-available"></small></p>
        <div id="lora-editor"></div><datalist id="lora-options"></datalist>
        <button type="button" class="secondary add-lora" data-action="add-lora">${icon("plus")}เพิ่ม LoRA</button></div>
      ${field("relationship","ความสัมพันธ์เริ่มต้น",300)}
      ${field("tips","เคล็ดลับเริ่มเรื่อง",2000,{area:true,help:"แสดงให้ผู้ใช้อ่านในโปรไฟล์และหน้าแชต เช่น สถานการณ์เริ่มต้นหรือแนวทางเข้าหาตัวละคร ไม่ใช่คำสั่งลับให้ AI"})}
      ${field("greeting","ข้อความเปิดบทสนทนา",1500,{area:true,required:true,help:"ใช้ *ข้อความ* บรรยายการกระทำ ตัวละครที่สร้างเก็บเป็นส่วนตัว"})}
      ${state.data.milestones.length ? `<div class="editor-section-heading"><h3>ภาพความทรงจำ</h3><p>เลือกภาพที่จะปรากฏอัตโนมัติและเก็บในอัลบั้มเมื่อคุยถึงแต่ละจุด</p></div>
      <div class="gallery-editor">${state.data.milestones.map(milestone=>`<div class="gallery-slot"><img id="gallery-preview-${milestone.id}" class="zoomable" data-action="zoom-image" src="${momentArt(source,milestone)}" alt="${milestone.title}" title="กดเพื่อดูภาพเต็ม"><strong>${milestone.title}</strong><small>คุยครบ ${milestone.threshold} รอบ</small><label class="secondary upload-label">${icon("image")}เลือกรูป<input type="file" accept="image/png,image/jpeg,image/webp" data-upload-target="${milestone.id}" class="sr-only"></label><button type="button" class="ghost" data-action="reset-moment-image" data-id="${milestone.id}">ใช้ภาพเริ่มต้น</button></div>`).join("")}</div>` : ""}
      <div class="editor-section-heading"><h3>ภาพตามสถานการณ์</h3><p>AI จะเลือกภาพที่ตรงกับฉากปัจจุบันมาแสดงเป็นพื้นหลังแชต และเก็บเข้าคอลเลกชันเมื่อปรากฏครั้งแรก เขียนคำอธิบายให้ชัด เช่น สถานที่ ท่าทาง อารมณ์ (ใช้กับห้องเดิมได้ทันที)</p></div>
      <div id="scene-editor" class="scene-editor"></div>
      <button type="button" class="secondary add-scene" data-action="add-scene">${icon("plus")}เพิ่มภาพตามสถานการณ์</button>
      ${editor.id ? '<div class="notice">รูปโปรไฟล์และภาพตามสถานการณ์จะอัปเดตในห้องเดิมด้วย ส่วนการแก้บุคลิกและประวัติจะใช้กับห้องใหม่</div>' : ""}
      <p class="form-error" id="character-error" role="alert"></p><div class="form-actions"><button type="button" class="ghost" data-action="close-modal">ยกเลิก</button><button class="primary" type="submit">${icon("sparkle")}${editor.id ? "บันทึกการแก้ไข" : "สร้างตัวละคร"}</button></div>
    </form>`);
    for (const element of $("#character-form").elements) {
      if (element.name && source[element.name] !== undefined) element.value = source[element.name];
    }
    if (duplicate) $("#char-name").value = `${source.name} (สำเนา)`.slice(0,60);
    renderScenes();
    renderLoras();
    fillLoraOptions();
    $("#char-name").focus();
  }

  async function upload(input) {
    const sceneIndex = /^scene:\d+$/.test(input.dataset.uploadTarget || "") ? Number(input.dataset.uploadTarget.slice(6)) : null;
    if (!editor || (!imageFields.has(input.dataset.uploadTarget) && sceneIndex === null) || editor.uploading) return;
    const file = input.files?.[0];
    if (!file) return;
    const activeEditor = editor;
    if (!["image/png","image/jpeg","image/webp"].includes(file.type) || file.size > 10 * 1024 * 1024) {
      input.value = "";
      throw new Error("เลือกภาพ PNG, JPEG หรือ WebP ขนาดไม่เกิน 10 MB");
    }
    editor.uploading = true;
    const submit = $("#character-form [type=submit]");
    submit.disabled = true;
    $("#character-error").textContent = "กำลังเตรียมและบันทึกรูปภาพ…";
    let bitmap;
    try {
      bitmap = await createImageBitmap(file);
      if (!bitmap.width || !bitmap.height || bitmap.width * bitmap.height > 40000000) throw new Error("รูปมีขนาดใหญ่เกินไป กรุณาย่อภาพก่อนอัปโหลด");
      const ratio = Math.min(1, 1200 / Math.max(bitmap.width,bitmap.height));
      const canvas = document.createElement("canvas");
      canvas.width = Math.max(1,Math.round(bitmap.width*ratio));
      canvas.height = Math.max(1,Math.round(bitmap.height*ratio));
      canvas.getContext("2d").drawImage(bitmap,0,0,canvas.width,canvas.height);
      // Re-encode in the browser, discarding EXIF metadata and never retaining the source filename.
      const encoded = canvas.toDataURL(file.type === "image/png" ? "image/png" : "image/jpeg", .88).split(",")[1];
      const result = await api("/api/media", {data:encoded});
      if (editor !== activeEditor || !$("#character-form")) return;
      if (sceneIndex !== null) {
        if (!editor.scenes[sceneIndex]) return;
        readScenes();
        editor.scenes[sceneIndex].media_id = result.id;
        renderScenes();
      } else if (input.dataset.uploadTarget === "portrait") {
        editor.portrait_id = result.id;
        $("#character-image-preview").src = result.url;
        $("#portrait-upload-status").textContent = "บันทึกรูปในเครื่องแล้ว";
        document.querySelectorAll(".art-choice").forEach(item=>item.classList.remove("active"));
      } else {
        editor.gallery[input.dataset.uploadTarget] = result.id;
        $(`#gallery-preview-${input.dataset.uploadTarget}`).src = result.url;
      }
      $("#character-error").textContent = "";
      toast("อัปโหลดภาพแล้ว กดบันทึกตัวละครเพื่อใช้ภาพนี้");
    } finally {
      bitmap?.close();
      activeEditor.uploading = false;
      if (submit.isConnected) submit.disabled = false;
      input.value = "";
    }
  }

  async function saveCharacter(form) {
    if (!editor || editor.uploading) throw new Error("กรุณารอให้อัปโหลดรูปเสร็จก่อน");
    const data = Object.fromEntries(new FormData(form));
    Object.assign(data,{age:Number(data.age),art:state.selectedArt,portrait_id:editor.portrait_id,
      gallery:editor.gallery,scenes:readScenes().map(({id,media_id,title,description,tier,min_turns,prompt,negative})=>({id,media_id,title:title||"",description,tier,min_turns,prompt:prompt||"",negative:negative||""})),
      image_loras:readLoras().filter(lora=>lora.name).map(({name,weight,trigger})=>({name,weight,trigger:trigger||""})),
      expectedVersion:editor.expectedVersion});
    await api(editor.id ? `/api/characters/${editor.id}/update` : "/api/characters",data);
    const wasEdit = !!editor.id;
    $("#modal").close(); editor = null;
    await refresh(); state.showArchived = false;
    await navigate("characters");
    toast(wasEdit ? "บันทึกแล้ว ห้องเดิมเก็บเรื่องราวและบุคลิกเดิมไว้" : "สร้างตัวละครพร้อมภาพของคุณแล้ว");
  }

  function showDetails(character) {
    openModal(esc(character.name), `<div class="character-profile"><img src="${art(character)}" alt="${esc(character.name)}"><div><span class="eyebrow">AI CHARACTER · ${character.age} YEARS</span><h3>${esc(character.subtitle || character.name)}</h3><p>${esc(character.description)}</p><div class="tag-row">${character.tags.map(tag=>`<span class="tag">${esc(tag)}</span>`).join("")}</div></div></div>
      ${character.tips ? `<div class="character-tips"><strong>เคล็ดลับเริ่มเรื่อง</strong><p>${esc(character.tips)}</p></div>` : ""}
      ${character.relationship ? `<div class="profile-detail"><strong>ความสัมพันธ์เริ่มต้น</strong><p>${esc(character.relationship)}</p></div>` : ""}
      <div class="profile-detail"><strong>ฉากเปิด</strong><p>${formatText(character.greeting)}</p></div>
      <div class="form-actions"><button class="secondary" data-action="clone-character" data-id="${character.id}">${icon("plus")}ทำสำเนา</button><button class="primary" data-action="profile-chat" data-id="${character.id}" ${character.archived ? "disabled" : ""}>${icon("chat")}เริ่มพูดคุย</button></div>`);
  }

  async function action(element) {
    const id = element.dataset.id;
    const character = state.data.characters.find(item=>item.id === id);
    switch (element.dataset.action) {
      case "create-character": openEditor(); return true;
      case "edit-character": if (character) openEditor(character); return true;
      case "clone-character": if (character) openEditor(character,true); return true;
      case "character-details": if (character) showDetails(character); return true;
      case "profile-chat": $("#modal").close(); await startChat(id); return true;
      case "add-lora":
        if (!editor) return false;
        if (editor.loras.length >= 5) { toast("ผูก LoRA ได้สูงสุด 5 ตัว", true); return true; }
        readLoras();
        editor.loras.push({name: "", weight: 0.8, trigger: ""});
        renderLoras();
        $(`.lora-row[data-index="${editor.loras.length - 1}"] input`)?.focus();
        return true;
      case "remove-lora":
        if (!editor) return false;
        readLoras();
        editor.loras.splice(Number(element.dataset.index), 1);
        renderLoras();
        return true;
      case "add-scene":
        if (!editor) return false;
        if (editor.scenes.length >= 50) { toast("เพิ่มได้สูงสุด 50 ภาพ", true); return true; }
        readScenes();
        editor.scenes.push({id: newId().slice(0, 12), media_id: "", title: "", description: "", tier: "common", min_turns: 0, prompt: "", negative: ""});
        renderScenes();
        $(`.scene-row[data-index="${editor.scenes.length - 1}"] textarea`)?.focus();
        return true;
      case "reload-image-options": await loadImageOptions(); return true;
      case "reset-image-settings": {
        const saved = await api("/api/images/settings", {});
        imageOptions = {...imageOptions, settings: saved};
        renderImageSettings();
        toast("คืนค่าเริ่มต้นแล้ว");
        return true;
      }
      case "zoom-image": {
        // Full-size preview layered inside the open dialog, so the editor (and unsaved edits) stay put.
        const src = element.getAttribute("src");
        if (!src) return true;
        const box = document.createElement("div");
        box.className = "image-lightbox";
        box.dataset.action = "close-lightbox";
        box.setAttribute("role", "dialog");
        box.setAttribute("aria-label", "ภาพเต็ม · กดที่ใดก็ได้เพื่อปิด");
        box.innerHTML = `<img src="${esc(src)}" alt="${esc(element.alt)}"><button type="button" class="icon-button" aria-label="ปิดภาพ">${icon("close")}</button>`;
        ($("#modal").open ? $("#modal") : document.body).append(box);
        box.querySelector("button").focus();
        return true;
      }
      case "close-lightbox": element.closest(".image-lightbox")?.remove(); return true;
      case "generate-scene": {
        if (!editor) return false;
        if (editor.uploading) { toast("กรุณารอให้ภาพก่อนหน้าเสร็จก่อน", true); return true; }
        readScenes();
        const index = Number(element.dataset.index);
        const scene = editor.scenes[index];
        if (!scene?.prompt?.trim()) { toast("กรอก Prompt สร้างภาพ (ภาษาอังกฤษ) ของฉากนี้ก่อน", true); return true; }
        const activeEditor = editor;
        const submit = $("#character-form [type=submit]");
        editor.uploading = true;
        submit.disabled = true;
        element.disabled = true;
        element.innerHTML = '<span class="spinner"></span>กำลังสร้างภาพ… (ประมาณ 30–60 วินาที)';
        try {
          const loras = readLoras().filter(lora => lora.name).map(({name, weight, trigger}) => ({name, weight, trigger: trigger || ""}));
          const negative = [$("#char-image_negative")?.value, scene.negative].map(text => (text || "").trim()).filter(Boolean).join(", ");
          const result = await api("/api/images/generate", {character_prompt: $("#char-image_prompt")?.value || "", prompt: scene.prompt, negative, loras});
          if (editor !== activeEditor || !$("#character-form")) return true;
          readScenes();
          scene.media_id = result.id;
          renderScenes();
          toast("สร้างภาพแล้ว ไม่ชอบกดสร้างใหม่ได้ · กดบันทึกตัวละครเพื่อใช้ภาพนี้");
        } finally {
          activeEditor.uploading = false;
          if (submit.isConnected) submit.disabled = false;
          if (element.isConnected) { element.disabled = false; element.innerHTML = `${icon("sparkle")}สร้างภาพด้วย AI (Stable Diffusion ในเครื่อง)`; }
        }
        return true;
      }
      case "remove-scene":
        if (!editor) return false;
        readScenes();
        editor.scenes.splice(Number(element.dataset.index), 1);
        renderScenes();
        return true;
      case "show-active-characters": state.showArchived=false; render(); return true;
      case "show-archived-characters": state.showArchived=true; render(); return true;
      case "pick-art":
        if (!editor) return false;
        state.selectedArt=element.dataset.art; editor.portrait_id="";
        $("#character-image-preview").src=`/assets/${state.selectedArt}.svg`;
        document.querySelectorAll(".art-choice").forEach(item=>item.classList.toggle("active",item===element));
        for (const milestone of state.data.milestones) {
          if (!editor.gallery[milestone.id]) $(`#gallery-preview-${milestone.id}`).src=momentArt({art:state.selectedArt},milestone);
        }
        return true;
      case "reset-moment-image": {
        delete editor.gallery[id];
        const milestone=state.data.milestones.find(item=>item.id===id);
        $(`#gallery-preview-${id}`).src=momentArt({art:state.selectedArt},milestone); return true;
      }
      case "archive-character":
        openModal("เก็บตัวละครเข้าคลัง?", `<p>เก็บ ${esc(character.name)} ออกจากรายการที่ใช้งาน บทสนทนา ความจำ และภาพที่ปลดล็อกแล้วจะยังอยู่ สามารถนำตัวละครกลับมาได้จากคลัง</p><div class="form-actions"><button class="ghost" data-action="close-modal">ยกเลิก</button><button class="primary" data-action="confirm-archive" data-id="${id}">เก็บเข้าคลัง</button></div>`); return true;
      case "confirm-archive": case "restore-character":
        await api(`/api/characters/${id}/archive`,{archived:element.dataset.action==="confirm-archive"});
        if ($("#modal").open) $("#modal").close();
        await refresh(); render(); toast("อัปเดตคลังตัวละครแล้ว"); return true;
      case "story-notes":
        openModal("สรุปเรื่องราวของห้องนี้", `<p>บันทึกสถานการณ์ เหตุการณ์สำคัญ และสิ่งที่ตกลงกันไว้ สรุปนี้จะช่วยรักษาเรื่องราวเมื่อแชตยาวขึ้น และใช้เฉพาะห้องนี้</p><form id="notes-form"><div class="field"><label for="story-notes-input">เรื่องราวจนถึงตอนนี้</label><textarea id="story-notes-input" maxlength="3000" rows="8">${esc(state.room.notes || "")}</textarea><small>คุณเป็นผู้เขียนและแก้ไขสรุปนี้ได้ สูงสุด 3,000 ตัวอักษร</small></div><p class="form-error" role="alert"></p><div class="form-actions"><button type="button" class="ghost" data-action="close-modal">ยกเลิก</button><button type="submit" class="primary">บันทึกสรุป</button></div></form>`); return true;
      case "branch-story":
        openModal("ลองเรื่องราวอีกเส้นทาง", `<p>สร้างห้องใหม่โดยคัดลอกบทสนทนาถึงข้อความที่เลือก พร้อมความจำที่บันทึกก่อนจุดนั้น ห้องเดิมยังอยู่ครบ สรุปเรื่องราวจะเริ่มว่างเพื่อไม่ให้มีเหตุการณ์จากอนาคตติดไปด้วย</p><div class="form-actions"><button class="ghost" data-action="close-modal">ยกเลิก</button><button class="primary" data-action="confirm-branch" data-id="${id}">${icon("book")}แตกเส้นเรื่อง</button></div>`); return true;
      case "confirm-branch": {
        const room=await api(`/api/rooms/${state.room.id}/branch`,{messageId:id});
        $("#modal").close(); await refresh(); await navigate("chat",room.id); toast("เปิดเส้นเรื่องใหม่แล้ว"); return true;
      }
      case "view-moment": {
        const current=state.data.characters.find(item=>item.id===element.dataset.character);
        const milestone=state.data.milestones.find(item=>item.id===element.dataset.milestone);
        const entry=state.data.gallery.find(item=>item.character_id===current.id && item.milestone_id===milestone.id);
        const saved=element.dataset.room === state.room?.id ? state.room.character : entry?.character || current;
        openModal(`${milestone.title} · ${esc(saved.name)}`,`<img class="modal-scene" src="${momentArt(saved,milestone)}" alt="${milestone.title}"><p>${milestone.description} — ${esc(saved.name)}</p><div class="form-actions"><button class="primary" data-action="close-modal">เก็บช่วงเวลานี้ไว้</button></div>`); return true;
      }
      default: return false;
    }
  }

  // Escape closes an open image preview first instead of the whole editor dialog.
  // Capture-phase keydown: stops Esc before the dialog turns it into a close request
  // (a dialog `cancel` event is not always cancelable in current Chrome).
  document.addEventListener("keydown", event => {
    const box = document.querySelector(".image-lightbox");
    if (event.key !== "Escape" || !box) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    box.remove();
  }, true);

  document.addEventListener("input", event => { if (event.target.closest("#image-settings-form")) updateImageSizeNote(); });
  document.addEventListener("change", event => { if (event.target.closest("#image-settings-form")) updateImageSizeNote(); });

  return {decorate,action,upload,saveCharacter,saveImageSettings,rememberRequest,finishRequest,draft,watchSummary};
})();
