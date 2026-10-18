# Background launcher (Windows)

repository มี `tools/start_background.py`, `start.bat`, `start.ps1`, `stop.bat` และ `stop.ps1` สำหรับเปิด/หยุดเบื้องหลังบน Windows หากใช้ checkout รุ่นเก่าที่ยังไม่มีไฟล์เหล่านี้ ให้อัปเดตโค้ดก่อน หรือใช้ `python app.py` แบบ foreground ตาม README

## เปิดและหยุดเบื้องหลัง

ใน PowerShell จากโฟลเดอร์โปรเจกต์ เลือกใช้คำสั่งตามต้องการ:

```powershell
.\start.bat
# หรือกำหนดพอร์ต
.\start.bat --port 3001
# หรือเปิด LAN โดยแทนด้วย IP จริง
.\start.bat --lan 192.168.1.100
```

ค่าเริ่มต้นเปิดเฉพาะ ELYRA บน localhost ไม่มี ngrok หน้าต่างคำสั่งปิดเมื่อเริ่มสำเร็จ รายละเอียดอยู่ใน `.data/start-info.txt` และ log `.data/server.*.log` การปิด browser ไม่หยุด server

```powershell
.\stop.bat
# หากใช้พอร์ตอื่น
.\stop.bat 3001
```

ตัวหยุดตรวจชื่อโปรเซสและพอร์ต หยุด ngrok HTTP ที่ส่งต่อมายังพอร์ตนั้นก่อน แล้วหยุด Python app.py ที่ตรงกัน หากต้องเปลี่ยน LAN/port/tunnel mode ให้หยุด instance เดิมก่อน ตัวเปิดไม่ restart instance ที่ตั้งค่าต่างกันเอง

## เปิด ngrok แบบเลือกใช้เอง

ต้องติดตั้ง ngrok และตั้ง authtoken ก่อน จากนั้นหยุด instance แบบ local เดิมแล้วรัน:

```powershell
.\start.bat --ngrok
```

launcher ใช้ credentials เดิมใน `.data/ngrok-access.json` หรือสร้างแบบสุ่ม ตรวจการล็อกอินก่อนรายงาน URL และปิด inspection URL อยู่ใน `.data/ngrok-url.txt` โหมดนี้ใช้ ngrok loopback API พอร์ต 4040 และไม่ปิด agent ของพอร์ตอื่นเอง

แอปบังคับ Basic login ทุกเส้นทางรวม localhost/LAN ในโหมด tunnel คนที่มี URL และรหัสผ่านเข้าถึงข้อมูลผู้ใช้เดียวกันได้ เก็บ credentials เป็นส่วนตัว ไม่ใส่ API key หรือ authtoken ในไฟล์นี้ ไม่ commit `.data`

หากต้องจัดการแต่ละ process เอง เปิด tunnel:

```powershell
ngrok http http://127.0.0.1:3000 --inspect=false
```

แล้วเริ่มแอปด้วย HTTPS origin ที่ได้จริงและไฟล์ credentials ที่เตรียมไว้:

```powershell
python app.py --tunnel-origin https://YOUR-HOST.ngrok-free.app --tunnel-credentials .data/ngrok-access.json
```

ไฟล์เป็น JSON ที่มี `username` และ `password` (รหัส ASCII สุ่มอย่างน้อย 16 ตัว) หาก URL เปลี่ยนต้องเริ่มแอปใหม่ด้วย origin ใหม่ `--lan PRIVATE_IP` เป็นตัวเลือกเพิ่มสำหรับ LAN ระบบตรวจ Host/Origin/token ตามเดิม ไม่เชื่อ `X-Forwarded-*` เพื่อข้าม checks

หยุดด้วย `.\stop.bat` แล้วเปิด `.\start.bat` เพื่อกลับสู่ localhost การเปิด tunnel แชร์แอปผู้ใช้เดียว ไม่ใช่ deployment หลายบัญชี
