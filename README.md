# Valren — AI Researcher Agent

Agent ติดตามเทคโนโลยี AI คัดเลือก GitHub repo, open model (LLM/CV), frontier LLM และ paper พร้อมอธิบายภาษาไทยและบันทึกความรู้ลง Notion

สถานะ: วางแผนพัฒนาแล้ว ยังไม่มี runtime หรือการเชื่อมต่อบริการจริง

- [ข้อกำหนดต้นทาง](docs/สรุปการออกแบบ%20Agent%20VARLEN%20(AI%20Researcher).md)
- [แผนพัฒนาและเกณฑ์รับงาน](docs/development-plan.md)
- [แบบร่าง Interest Profile](docs/interest-profile.template.md)

ใช้ `valren` เป็นชื่อ directory และ Python package; คงชื่อ persona `VARLEN` ตามเอกสารต้นทางจนกว่าจะตัดสินเรื่องชื่อ

ไฟล์โค้ด การตั้งค่า เอกสาร และข้อมูล runtime ของงานนี้ต้องอยู่ภายใน directory นี้ ห้าม mount หรืออ่าน secrets และ `.hermes` ของ agent อื่น การเชื่อมต่อบริการภายนอกและการ deploy ยังไม่ได้เกิดขึ้นจากขั้นวางแผนนี้
