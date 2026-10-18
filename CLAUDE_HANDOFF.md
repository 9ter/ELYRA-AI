# ELYRA AI — Project handoff for Claude

อัปเดต memory วันที่ 2026-10-18 หากสถานะเปลี่ยน ให้ยึดโค้ดปัจจุบันและ Status/Work Log ล่าสุดใน `AGENTS.md` ร่วมกัน รายละเอียดเดโมเดิมด้านล่างเป็นข้อมูลจากวันที่ 2026-10-17 และอาจถูกพัฒนาต่อแล้ว

## สถานะล่าสุดสำหรับรับงานต่อ

- ขอบเขตที่ผู้ใช้เลือกคือ **MVP ในเครื่อง** บน Desktop/Mobile Browser ก่อน ไม่มีงานเปิดบริการหลายผู้ใช้ในรอบนี้
- ผู้ใช้อนุญาต LAN แล้ว: รัน `python app.py --lan 192.168.1.181` เพื่อใช้ทั้ง localhost และ IP นี้ ค่าเริ่มต้นไม่มี flag ยังเป็น loopback มี Host/Origin/token checks และทุกอุปกรณ์ใช้ข้อมูลชุดเดียวกัน เพิ่ม `enable-lan-firewall.ps1` สำหรับ Administrator หากจำเป็น แต่เครื่องนี้มีกฎ Allow Python บน Public อยู่แล้ว จึงไม่ได้แก้ Firewall/Router ทดสอบ LAN-IP ผ่านเบราว์เซอร์บนพีซีแล้ว ยังไม่ได้ทดสอบจากอุปกรณ์อื่นจริง ชุดทดสอบล่าสุด 89 ข้อผ่าน
- UI เปลี่ยนเป็นสไตล์ Toomics: chat overlay, หน้ารายละเอียด และคอลเลกชัน (`toomics.css`, `detail.js`) สคริปต์ browser QA เดิมบางตัวต้องปรับ selector ก่อนใช้
- แก้พื้นหลังห้องเก่าแล้ว: ใช้รูปของตัวละครฉบับปัจจุบัน แต่บุคลิก/ประวัติใน room snapshot ยังเหมือนเดิม
- **สรุปเรื่องราว · AUTO** รวมช่องเดิมกับสรุปอัตโนมัติ ไม่มีเกียร์ให้กรอกสรุปเอง สถานะอ่านจาก `GET /api/rooms/{id}/summary` ทุก 3 วินาทีระหว่างหน้าแชทที่มองเห็นอยู่ ไม่เรียกโมเดลเพิ่มจากการ polling ไม่รบกวนข้อความร่างหรือ focus บันทึกมือเดิมยังเก็บในหัวข้อพับและในบริบท/export
- Context Cloud 96,000 / Ollama 6,400 UTF-8 bytes; automatic older-chat summary ทำเบื้องหลังที่เกณฑ์ Cloud 40/24 KB หรือ Ollama 2,400/1,200 bytes (trigger/keep) ยังเก็บแชทล่าสุดแบบเต็มและไม่มีการลบประวัติจริง
- ผู้ใช้เปลี่ยนใจให้ **AI เลือกความยาวตามจังหวะ** แล้ว: SHORT 1–2, MEDIUM 2–4, LONG 4–6 ช่วง แทนข้อกำหนดเดิมที่บังคับยาวทุกครั้ง รักษาคำบรรยายฉาก ท่าทาง สีหน้าและอารมณ์ มีตัวช่วยลดคำขึ้นต้นซ้ำและความยาวซ้ำใน `context.py`
- ฉากใช้ tagged images + marker/fallback picker + การหมุนภาพ variant และคำอธิบายจาก prompt เดิม ดู `elyra/scenes.py` ไม่ใช่แค่ปลดล็อกภาพตาม 1/3/6 รอบอย่างเดียวแล้ว
- มี `elyra/imagegen.py` สำหรับ Local Forge/A1111 ผ่าน loopback; **Live2D ยังเป็นแนวคิดที่คุยกัน ไม่ได้ลง renderer หรือโมเดล rig**
- กติกาเนื้อหาแยกตาม room mode แล้ว ให้ตรวจ `domain.CONTENT_RULES` และบันทึกการตัดสินใจของผู้ใช้จาก Claude แทนข้อความเดโมเก่าในเอกสารนี้ การยืนยันอายุยังเป็น self-declaration; ผลทดสอบโมเดลไม่ใช่การอนุมัติจาก provider
- ผลล่าสุด: Claude รายงาน **80 offline tests ผ่าน**; Codex ยืนยันรอบ AUTO ก่อนหน้านั้น 79 ข้อพร้อม browser Desktop/Mobile โดยใช้ฐานข้อมูลจำลองและไม่เรียก API เสียเงิน
- **สิ่งติดขัดล่าสุดตาม Claude:** xAI HTTP 402 เครดิตหมด จึงยังยืนยันการแก้ adaptive length รอบล่าสุดแบบ live ไม่ได้ อย่าทดสอบซ้ำเสียเงินโดยไม่จำเป็น ปัญหานี้ต่างจาก invalid-key เดิมที่แก้แล้ว
- ตรวจเฉพาะ health/bootstrap รอบ memory นี้: localhost:3000 พร้อมตอบ, 5 ตัวละคร / 2 ห้อง / 104 รอบผู้ใช้, default xai/grok-4.3 ไม่ได้เรียกโมเดลหรือแก้แชท ตรวจ PID จริงก่อน restart เสมอ

## 1. ผู้ใช้กำลังสร้างอะไร

ELYRA คือ Web Application สำหรับ AI Character Roleplay Chat ได้แรงบันดาลใจจาก Character.AI และ Toomics Chat ผู้ใช้สร้างตัวละคร กำหนดบุคลิก ประวัติ รูปลักษณ์ และความสัมพันธ์ แล้วสนทนาต่อเนื่องกับตัวละครนั้น

ประสบการณ์ที่ต้องการคือ **ตัวละครที่จำเรื่องราวได้ พร้อมภาพประกอบและอัลบั้มสะสมตามความคืบหน้าของเรื่อง** เริ่มจาก Desktop/Mobile Browser ก่อน และค่อยขยายเป็น Native Mobile App

ผู้ใช้ต้องการให้แอปเดียวรองรับแหล่งประมวลผล AI สองแบบ:

- **Cloud API:** xAI หรือ OpenAI
- **Local:** โมเดลที่รันผ่าน Ollama

ตัวละคร แชต และความจำเป็นของแอป จึงเปลี่ยน provider ได้โดยยังใช้ข้อมูลห้องเดิม ไม่แยกเป็นสองเว็บ

ความต้องการระยะยาวมีทั้งเนื้อหาทั่วไปและโหมดผู้ใหญ่ภายใต้ข้อกำหนดที่เกี่ยวข้อง ปัจจุบันเดโมอนุญาตโรแมนซ์และธีมดราม่า แต่ system prompt ไม่อนุญาตเนื้อหาทางเพศโจ่งแจ้ง โหมด 18+ ยังเป็นเพียงการยืนยันอายุด้วยตนเอง

## 2. สิ่งที่ทำเสร็จใน Local MVP

ผู้ใช้ยืนยันขอบเขต **MVP ในเครื่องให้ครบก่อน** ยังไม่เปิดบริการหลายผู้ใช้ รอบล่าสุดเพิ่มเคล็ดลับตัวละคร, รูปโปรไฟล์และภาพ milestone อัปโหลด, แก้ไข/ทำสำเนา/เก็บคลัง/นำกลับ, snapshot ตัวละครรายห้อง, สรุปเรื่องราวที่ผู้ใช้เขียนเอง, แตกเส้นเรื่อง, ฉบับร่างในแท็บ, request ID ป้องกัน retry ซ้ำหลัง commit และ context bounds แล้ว ภาพปลดล็อกแสดงในแชตและอัลบั้ม รูปอยู่ใน SQLite; export JSON รวมรูป base64

ไฟล์ใหม่: `elyra/media.py`, `elyra/context.py`, `public/mvp.js`, `public/mvp.css`, `tests/test_mvp.py`, `tools/browser_mvp_qa.py` ฐานข้อมูลเดิมสำรองก่อน migration ที่ `.data/elyra.before-mvp.sqlite3` ห้ามลบข้อมูลจริงของผู้ใช้หรือห้องทดสอบ xAI ที่ Claude สร้าง

- หน้า Discover พร้อมค้นหา ประเภทตัวละคร และรายการโปรด
- ตัวละครต้นแบบ 4 คน: Luna, Kael, Mira และ Ren
- ฟอร์มสร้างตัวละครส่วนตัว: ชื่อ อายุ คำอธิบาย บุคลิก ประวัติ รูปลักษณ์ ความสัมพันธ์ และคำทักทาย
- ห้องแชตต่อเนื่องพร้อม streaming และการแสดงการกระทำด้วย `*ข้อความ*`
- เปลี่ยน provider รายห้อง โดยรักษาประวัติและความจำไว้
- บันทึก/ลบความจำด้วยตนเอง โดยแยกตามห้อง
- เริ่มห้องใหม่กับตัวละครเดิม และลบห้องพร้อมข้อมูลที่เกี่ยวข้อง
- แกลเลอรีปลดล็อกภาพตามจำนวนรอบสนทนา
- หน้าตั้งค่า provider/model, โหลดรายชื่อโมเดล, ชื่อผู้ใช้ และตัวเลือกยืนยันอายุ
- ส่งออกตัวละครและบทสนทนาเป็น JSON
- Responsive layout: เมนูและแผงข้อมูลตัวละครพับได้บนจอเล็ก

**Demo mode ใช้คำตอบที่เขียนไว้ล่วงหน้า ไม่ใช่ LLM** มีไว้ทดสอบ flow โดยไม่ต้องมี key หรือเสียค่า API

## 3. Stack และแผนที่โค้ด

ตอนนี้ใช้ **Python standard library + SQLite + HTML/CSS/vanilla JavaScript** ไม่มี npm, framework frontend หรือ dependency Python ภายนอก ไม่ต้องเปลี่ยน stack เพื่อให้เริ่มรันได้

| ไฟล์ | หน้าที่ |
| --- | --- |
| `app.py` | `ThreadingHTTPServer`, เสิร์ฟ `public/`, API, ตรวจ input/สิทธิ์, ประกอบบริบทแชต, ส่ง stream และควบคุมงานรายห้อง |
| `elyra/domain.py` | ตัวละครเริ่มต้น, `MILESTONES`, validation, system prompt และ scripted demo replies |
| `elyra/providers.py` | อ่าน config/secrets, โหลดโมเดล และ adapter สำหรับ stream ของแต่ละ provider |
| `elyra/store.py` | SQLite schema, room/message/memory/settings CRUD และ commit รอบสนทนาพร้อมปลดล็อกภาพ |
| `public/index.html` | หน้าเริ่มต้น โหลด CSS/JavaScript |
| `public/app.js` | SPA แบบ hash routing, render หน้าต่าง ๆ, form/events, อ่าน NDJSON stream และ modal |
| `public/styles.css` | ธีมเข้ม โทน lavender และ responsive breakpoints |
| `public/assets/` | ภาพ SVG ต้นฉบับในโปรเจกต์ ไม่พึ่งบริการภาพภายนอก |
| `tools/build_assets.py` | สร้างภาพ SVG ตัวละครและภาพความทรงจำใหม่ |
| `tests/test_app.py` | Integration tests และ provider stream tests โดยใช้ข้อมูล/บริการจำลอง |
| `tools/browser_qa.py` | Chrome DevTools smoke test และ screenshot บน Desktop/Mobile |
| `README.md` | คู่มือเปิดเดโม ตั้งค่า provider และข้อจำกัด |

ข้อมูลรันจริงอยู่ใน `.data/elyra.db` ส่วนตารางหลักคือ `characters`, `rooms`, `messages`, `memories`, `unlocks`, `settings` ใช้ WAL และเปิด connection แยกตาม operation

ค่า provider/model/mode อยู่ที่ห้อง แต่ละข้อความบันทึก provider/model ที่ใช้สร้างคำตอบด้วย รายการโปรดเก็บใน `localStorage` ของเบราว์เซอร์

## 4. เส้นทางของหนึ่งรอบสนทนา

1. Frontend ส่ง `POST /api/rooms/{id}/chat` พร้อม `{ "text": "..." }`
2. Backend ตรวจข้อความและจองห้องใน `busy_rooms` ป้องกันสร้างคำตอบพร้อมกันในห้องเดียว
3. ประกอบ system prompt จากตัวละครและความจำที่ผู้ใช้บันทึก แล้วแนบข้อความล่าสุดไม่เกิน 21 ข้อความและข้อความใหม่
4. เรียก scripted demo หรือ provider ที่ห้องเลือกไว้
5. Adapter แปลง stream ให้เป็นข้อความชิ้นย่อย
6. Backend ส่ง **NDJSON** ให้ frontend โดย event มี `delta`, `done`, `error`
7. เมื่อคำตอบเสร็จและไม่ว่าง จึงบันทึกข้อความผู้ใช้กับ AI เป็นคู่ พร้อมตรวจ milestone ภายใน transaction
8. ส่ง `done` พร้อมข้อมูลห้องล่าสุดและรายการภาพที่เพิ่งปลดล็อก

หาก stream ล้มเหลวก่อน commit จะไม่บันทึกคู่ข้อความหรือปลดล็อกภาพ Frontend โหลดห้องกลับมาจาก backend และคืนข้อความที่ยังส่งไม่สำเร็จลงช่องพิมพ์

มี `requestId` ต่อคำขอ เก็บใน sessionStorage ของแท็บและบันทึกใน transaction เดียวกับข้อความ Backend คืน `done` โดยไม่เรียกโมเดลเมื่อคำขอเดิม commit แล้ว; ใช้ ID เดิมกับข้อความอื่นถูกปฏิเสธ สตรีมที่ไม่จบไม่ถูก commit และอาจเสียค่า API เมื่อเรียกใหม่

บริบทใช้ UTF-8 bytes เป็นขอบเขต (Cloud 48,000 / Ollama 6,400) เลือกคู่ข้อความล่าสุดที่ใส่ได้พร้อมบุคลิก ความจำล่าสุด และสรุปที่ผู้ใช้เขียนเอง ไม่ใช่ token counter หรือ automatic summarization

## 5. รายละเอียด provider ที่มีในโค้ด

| Provider | วิธีเรียกปัจจุบัน |
| --- | --- |
| `demo` | `demo_reply()` แล้วทยอยส่งข้อความจำลอง |
| `openai` | `/v1/responses`, `stream: true`, `store: false` |
| `xai` | `/v1/chat/completions`, `stream: true` |
| `ollama` | `/api/chat` บน loopback, อ่าน NDJSON จาก Ollama |

- Backend เก็บประวัติเอง ไม่ใช้ conversation ID ของ provider เป็นข้อมูลหลัก
- ไม่มีการ fallback จาก Local ไป Cloud อัตโนมัติ
- `OLLAMA_BASE_URL` อนุญาตเฉพาะ loopback ในเดโม
- ป้าย configured ในหน้า Settings หมายถึงพบการตั้งค่าหรือ key ไม่ได้หมายถึงผ่านการเชื่อมต่อจริง
- ไม่มีค่า Cloud model ตายตัว ต้องโหลด/ระบุโมเดลที่บัญชีใช้ได้
- `store: false` ในโค้ด OpenAI ไม่ควรถูกอธิบายว่าเท่ากับไม่มีการเก็บข้อมูลทุกประเภทโดย provider

## 6. API หลัก

| Method / path | ใช้ทำอะไร |
| --- | --- |
| `GET /api/health` | ตรวจเซิร์ฟเวอร์ |
| `GET /api/bootstrap` | โหลดตัวละคร ห้อง ตั้งค่า milestones/gallery และ token |
| `GET /api/models?provider=...` | ขอรายชื่อโมเดลของ provider ที่เลือก |
| `GET /api/rooms/{id}` | โหลดห้องพร้อมข้อความ ความจำ และภาพปลดล็อก |
| `GET /api/export` | ส่งออกข้อมูล ต้องแนบ token |
| `POST /api/characters` | สร้างตัวละคร |
| `POST /api/characters/{id}/update` | แก้ไขพร้อม expectedVersion; เก็บ snapshot ห้องเดิม |
| `POST /api/characters/{id}/archive` | เก็บคลังหรือนำกลับ |
| `POST /api/media` | อัปโหลด PNG/JPEG base64 ที่ตรวจแล้ว |
| `GET /media/{id}` | อ่านภาพจาก SQLite |
| `POST /api/rooms` | สร้างห้อง |
| `POST /api/settings` | บันทึกค่าเริ่มต้น |
| `POST /api/rooms/{id}/chat` | ส่งข้อความและรับ NDJSON stream |
| `POST /api/rooms/{id}/configure` | เปลี่ยน provider/model/mode |
| `POST /api/rooms/{id}/memory` | เพิ่มความจำ |
| `POST /api/rooms/{id}/forget` | ลบความจำด้วย `memoryId` |
| `POST /api/rooms/{id}/notes` | บันทึกสรุปของผู้ใช้เฉพาะห้อง |
| `POST /api/rooms/{id}/branch` | แตกเส้นเรื่องถึง messageId ฝั่ง assistant |
| `POST /api/rooms/{id}/delete` | ลบห้องและข้อมูลที่เกี่ยวข้อง |

Mutation ทุกตัวต้องแนบ `X-Elyra-Token` ที่ได้รับจาก bootstrap เป็น token สุ่มต่อการรันเซิร์ฟเวอร์ ใช้ป้องกันคำขอข้ามแหล่งกำเนิดในเดโม **ไม่ใช่ user authentication** มีการตรวจ Host/Origin และเสิร์ฟไฟล์ได้เฉพาะภายใต้ `public/`

## 7. อะไรยังเป็นเพียงการจำลอง

- **ภาพ:** มี SVG เตรียมไว้และภาพอัปโหลด PNG/JPEG ไม่ได้ generate จาก AI สด
- **Event detection:** ปลดล็อกที่ 1, 3, 6 รอบสนทนา ยังไม่ได้ตรวจเหตุการณ์เชิงความหมาย
- **ความสัมพันธ์:** progress ตามจำนวนรอบ ไม่ใช่ระบบจำลองอารมณ์หรือ relationship engine
- **Memory:** ผู้ใช้บันทึกเอง ยังไม่มีการสกัดความจำอัตโนมัติหรือสรุปแชตเก่า
- **Context:** มี byte bounds และเลือกคู่ข้อความล่าสุด ยังไม่มี tokenizer ของแต่ละโมเดลหรือสรุปอัตโนมัติ
- **Appearance:** คำอธิบายรูปลักษณ์ส่งเข้าแชต รูปเลือกจากเดโมหรืออัปโหลดเองได้
- **Gallery lock:** เป็นสถานะสะสมในแอป ไฟล์ภาพยังเป็น static assets ไม่ใช่ protected premium media
- **18+:** self-declaration และคำสั่งใน system prompt ยังไม่มี production age verification/moderation
- **Deployment:** single-user localhost เท่านั้น ยังไม่มีบัญชีผู้ใช้ การแยก tenant การชำระเงิน หรือ native app

## 8. สถานะการทดสอบและปัญหาที่ทราบ

- ตรวจล่าสุด: offline tests **36 รายการผ่าน** รวมรูปและการเสิร์ฟที่ปลอดภัย, แก้ไขแบบ version, snapshot ห้องเดิม, archive/restore, retry deduplication, notes, branch, export media, migration backup และ context bounds นอกเหนือจากชุดเดิม
- Chrome smoke test ผ่าน Desktop และ mobile viewport รวมสร้างตัวละคร แชต ความจำ แกลเลอรี ตั้งค่า ยืนยันธีมผู้ใหญ่ โหลดประวัติ และไม่มี console error
- ภาพหน้าจออยู่ใน `.qa/` ซึ่งไม่ควร commit
- **อัปเดต 2026-10-17:** หลังผู้ใช้เพิ่ม Billing และเปลี่ยนคีย์ xAI model listing ผ่าน พบ 14 โมเดล และทดสอบ `grok-4.7` ผ่าน `/v1/responses` สำเร็จ HTTP 200 / completed พร้อมคำตอบภาษาไทยหนึ่งครั้ง สถานะปัญหา authentication เดิมแก้แล้ว
- **บันทึกเพิ่มเติมจาก Claude:** ใน memory ร่วม Claude รายงานว่า `grok-4.3` ผ่าน `/v1/chat/completions` แบบไม่สตรีมตอบภาษาไทยและคำขอเรื่องแต่งสำหรับผู้ใหญ่ที่ยินยอมได้ โดยไม่ปฏิเสธ Codex ไม่ได้ทดสอบคำขอนี้ซ้ำ ผลการตอบครั้งนั้นยังไม่ยืนยันความสม่ำเสมอหรือการอนุมัติเปิดบริการ ERP จากผู้ให้บริการ
- Codex ตรวจ AUP/Enterprise Terms จากเว็บไซต์ทางการแล้ว บันทึกแหล่งอ้างอิงและขอบเขตข้อค้นพบอยู่ในหัวข้อ Adult Roleplay Findings ของ `AGENTS.md` การเลือกโมเดล โหมดเนื้อหาของแอป และสิทธิ์ตามนโยบายต้องประเมินแยกกัน ยังไม่มีการเปลี่ยน system prompt เพื่อเปิด ERP
- Claude ยืนยัน live streaming ของ grok-4.3 ผ่านแอปแล้ว (137 deltas, commit และ unlock) ตัวละครและห้องจริงยังต้องคงอยู่ การทดสอบ offline/browser รอบ MVP ใช้ DB แยกและไม่เรียก API เสียเงิน OpenAI/Ollama ยังไม่ยืนยัน live inference ห้ามคัดลอก key ลงเอกสารหรือ output
- ครั้งที่ตรวจ Ollama ยังเชื่อมต่อไม่ได้ ต้องเปิดบริการและดาวน์โหลดโมเดลก่อน
- เคยเกิด `ERR_CONNECTION_REFUSED` เพราะ Python server ไม่ได้รัน ต่อมาเปิดเป็น hidden background process และตรวจหน้าแรก HTTP 200 / health สำเร็จแล้ว ตรวจใหม่ก่อนสรุปว่ายังทำงานอยู่
- Runtime PID/log อยู่ใน `.data/server.pid`, `.data/server.log`, `.data/server-error.log` PID อาจเก่า ต้องตรวจ process ปัจจุบันก่อนหยุดหรือเริ่มใหม่

## 9. เปิดและตรวจงาน

```powershell
cd "D:\ELYRA AI"
python app.py
# เปิด http://localhost:3000

python -m unittest discover -s tests -v
python -m compileall -q app.py elyra tools
```

`start.bat` และ `start.ps1` เรียก `python app.py` เช่นกัน เมื่อแก้ Python code ต้อง restart process เพื่อโหลดโค้ดใหม่ อย่าเปิดเซิร์ฟเวอร์ซ้ำทับพอร์ตเดิม

`tools/browser_qa.py` และ `tools/browser_mvp_qa.py` ต้องมี Chrome สำหรับ QA เปิด DevTools ที่พอร์ต 9223 ก่อน สคริปต์สร้างฐานข้อมูลทดสอบแยกใน `.qa/` ไม่ใช้แชตจริงและไม่เรียก AI จริง ทั้งสองชุดผ่าน Desktop/Mobile ไม่มี console error รวม upload/edit/archive/branch/notes/draft และภาพ inline

## 10. แนวทางพัฒนาต่อ

รายการต่อไปนี้เป็นข้อเสนอสำหรับจัดลำดับ ไม่ใช่งานที่ Claude ถูกมอบหมายหรือทำเสร็จแล้ว:

1. ทดสอบ live OpenAI/Ollama เมื่อผู้ใช้เตรียม credential/runtime; xAI ผ่านแล้ว
2. ต่อยอด byte bounds และ manual recap เป็น model-aware token budgeting และสรุปอัตโนมัติหากจำเป็น
3. เพิ่มการตรวจเหตุการณ์เป็น structured data โดยให้ backend ตรวจเงื่อนไขก่อนปลดล็อกภาพ
4. เพิ่มการนำเข้า export และเครื่องมือจัดการข้อมูลหากผู้ใช้ต้องการ; แก้ไข/เวอร์ชันตัวละครและ snapshot ห้องเก่าทำแล้ว
5. ก่อนเปิดให้หลายคนใช้ เพิ่ม authentication, per-user authorization, rate limits, privacy controls, moderation และ age assurance ที่เหมาะสม
6. หลังพิสูจน์คุณภาพบทสนทนา ค่อยเพิ่มภาพสด ระบบผู้สร้าง รายได้ และ Native App

เก็บสถาปัตยกรรม provider adapter และข้อมูลหลักของแอปไว้แยกกัน การเปลี่ยนโมเดลไม่ควรทำให้ประวัติ/ความจำหาย และอย่าใช้ fallback ที่ส่งข้อมูล Local ออก Cloud โดยไม่แจ้ง

## 11. การทำงานร่วมกับ Codex

อ่าน `AGENTS.md` ก่อนเริ่มและระบุ task/files ที่จะรับผิดชอบ ตอนตรวจเอกสารนี้ยังมีทั้งไฟล์แก้ไขและไฟล์ใหม่ที่ไม่ commit อย่า reset, clean หรือเขียนทับเพื่อทำ working tree ให้สะอาด

หากจะเปลี่ยน schema, API contract หรือรูปแบบ stream ให้บันทึกผลกระทบต่ออีกฝั่งก่อนลงมือ แบ่งงานตามไฟล์เมื่อทำคู่ขนาน หลังจบระบุ validation และสิ่งที่ยังไม่ยืนยันใน Work Log

อย่า print, log, commit หรือส่งต่อเนื้อหา `.env` / `xAi_api_key.text` ราคาหรือชื่อโมเดลจาก memory อาจล้าสมัย ต้องตรวจใหม่เมื่อต้องใช้ตัดสินใจจริง
