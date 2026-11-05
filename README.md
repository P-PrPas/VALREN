# Valren — AI Researcher Agent

Agent ติดตามเทคโนโลยี AI คัดเลือก GitHub repo, open model (LLM/CV), frontier LLM และ paper พร้อมอธิบายภาษาไทยและบันทึกความรู้ลง Notion

สถานะ: มี CLI foundation และ offline tests แล้ว ยังไม่มีการเชื่อมต่อบริการจริง

รันจาก directory นี้ (หรือตั้ง `VALREN_HOME` เป็น absolute path ของ checkout):

```bash
PYTHONPATH=src python3 -m valren.cli doctor
PYTHONPATH=src python3 -m valren.cli radar --dry-run --fixture tests/fixtures/candidates.json
PYTHONPATH=src python3 -m unittest discover -v
```

- [ข้อกำหนดต้นทาง](docs/สรุปการออกแบบ%20Agent%20VARLEN%20(AI%20Researcher).md)
- [แผนพัฒนาและเกณฑ์รับงาน](docs/development-plan.md)
- [แบบร่าง Interest Profile](docs/interest-profile.template.md)

ใช้ `valren` เป็นชื่อ directory และ Python package; คงชื่อ persona `VARLEN` ตามเอกสารต้นทางจนกว่าจะตัดสินเรื่องชื่อ

ไฟล์โค้ด การตั้งค่า เอกสาร และข้อมูล runtime ของงานนี้ต้องอยู่ภายใน directory นี้ ห้าม mount หรืออ่าน secrets และ `.hermes` ของ agent อื่น การเชื่อมต่อบริการภายนอกและการ deploy ยังไม่ได้เกิดขึ้นจากขั้นวางแผนนี้
