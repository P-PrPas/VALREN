# แผนพัฒนา Valren / VARLEN

วันที่: 6 พฤศจิกายน 2026

## 1. เป้าหมายและสถานะข้อกำหนด

อ้างอิง [เอกสารออกแบบต้นทาง](สรุปการออกแบบ%20Agent%20VARLEN%20(AI%20Researcher).md) โดยไม่เปลี่ยนข้อเสนอเดิมให้กลายเป็นข้อกำหนดที่ผู้ใช้ยืนยันแล้ว

**ยืนยันแล้ว:** เป็น specialist แยกจาก Malren ใน homelab; ติดตาม repo ยอดนิยมที่ยังไม่เคยแนะนำ, open model ทั้ง LLM/CV, frontier LLM และ paper ทั้งใหม่/เก่า; ความรู้ต้องอยู่ใน Notion second brain; งานพัฒนาทั้งหมดอยู่ภายใน `valren/`

**แนวทางที่เสนอในแผนนี้:** เริ่มจาก Radar รายวัน แล้วเพิ่ม Tutor ตามคำขอ ใช้ script จัดการข้อมูลและสิทธิ์ ส่วน LLM จัดอันดับ สรุป และสอน ไม่มีสิทธิ์รันโค้ดจากแหล่งที่อ่าน

**ยังต้องตัดสิน:** Interest Profile จริง, งบรายเดือน, รุ่น/provider ของ LLM, ช่องทางและเวลาส่งจริง, persona, ขอบเขต verification และสิทธิ์เชื่อมต่อบริการ ส่วนที่ยังไม่มีคำตอบไม่ขวางการพัฒนาแบบ offline แต่ต้องมีค่าชัดก่อนเปิดงานที่ใช้เงินจริงหรือส่งข้อความอัตโนมัติ

## 2. MVP และค่าเริ่มต้นที่เสนอ

MVP คือค้นพบข้อมูลทั้งสี่กลุ่ม คัดเฉพาะเรื่องที่เกี่ยวข้อง สรุปภาษาไทยพร้อมหลักฐาน เก็บ Notion และส่ง digest โดยไม่แนะนำรายการเดิมซ้ำตามปกติ

- Radar วันละครั้ง; เวลาที่เสนอ 08:00 `Asia/Bangkok`; quiet hours 23:00–07:00 ตรวจ ณ เวลาส่งจริง รวม retry
- Digest ไม่เกิน 3 รายการต่อวันรวมทุกประเภท ไม่เติมให้ครบเมื่อไม่มีของดี; จำกัด pending digest ต่อวันด้วย
- Deep-dive ไม่เกิน 1 เรื่องต่อสัปดาห์เป็นค่าเริ่มต้น เริ่มจากผู้ใช้สั่งเอง ยังไม่ตั้งงานใช้ LLM อัตโนมัติ
- เฟสแรกไม่ส่ง breaking alert; เพิ่มเมื่อเกณฑ์เรื่องใหญ่และคุณภาพของ Radar ชัดแล้ว
- ดึงย้อนหลังเริ่มต้น 7 วันและมี overlap เพื่อรับข้อมูลที่มาช้า; paper เก่าสำหรับ Tutor ไม่ติดหน้าต่างนี้
- จำกัด candidate เริ่มต้น 100 รายการต่อรอบก่อน LLM; เก็บจำนวนที่ถูกตัดเพื่อเห็นข้อจำกัด coverage
- งบเงินจริงไม่มีค่าเดา: ถ้ายังไม่กำหนด budget และราคาของโมเดล ให้รัน dry-run/ไม่มี LLM เท่านั้น

ยังไม่เพิ่ม vector database, web dashboard, multi-agent debate หรือ local model serving เพราะยังไม่จำเป็นต่อวงจรหลัก

## 3. โครงสร้างระบบ

เสนอ Python 3.12+, SQLite จาก standard library, HTTP client และ parser สำหรับ Atom/RSS เท่าที่จำเป็น พร้อม pytest สำหรับ logic สำคัญ ล็อก dependency เมื่อเริ่ม implementation และตรวจ runtime ของ Hermes ก่อนเลือก image จริง

วงจร Radar: fetch → normalize → deduplicate → filter/rank → summarize/verify → persist Notion → queue digest → deliver

แบ่งเป็นโมดูลตามหน้าที่ใน package เดียว ไม่ต้องแยก microservices:

- `sources`: GitHub, Hugging Face, arXiv และ official announcements; คืนโครงสร้างข้อมูลร่วม ไม่คืนคำสั่งให้ agent ทำตาม
- `pipeline`: จัดลำดับงาน เพดานรายการ เวลา retry และ lock ป้องกันรอบซ้อน
- `store`: SQLite สำหรับ candidates, aliases, checkpoints, job state, delivery outbox และ usage
- `notion`: ตรวจ schema, query/upsert รายการ และแก้เฉพาะ field/block ที่ระบบเป็นเจ้าของ
- `llm`: structured output ของคะแนน สรุปและหลักฐาน; เลือก provider เดียวก่อนตามบัญชีและงบจริง
- `delivery`: Discord webhook ก่อน; Telegram command/Tutor ในเฟสถัดไป
- `tutor`: อ่านแหล่งที่อนุญาต สร้างบทเรียน แล้วบันทึกผ่าน Notion writer เดิม

คำสั่ง CLI ที่จะสร้าง: `doctor`, `radar --dry-run`, `radar`, `sync-library`, `retry-deliveries` และ `tutor <id-or-url>` แต่ละคำสั่งต้องมี exit code และ run ID ที่ตรวจสอบได้

Hermes เป็นชั้นสนทนาในเฟส 3 ใช้ worker เดิมทำงานผ่าน interface ที่ตรวจสิทธิ์แล้ว ไม่ให้โมเดลเรียก arbitrary shell หรือ raw Notion API ต้องตรวจ Hermes version, tool/plugin interface, Telegram และ agent_net ที่ติดตั้งจริงก่อนออกแบบ adapter ไม่สมมติชื่อ API หรือความสามารถที่ยังไม่ตรวจ

โครงสร้างไฟล์เป้าหมาย ซึ่งจะสร้างเฉพาะเมื่อถึงเฟสที่ใช้งาน:

```text
valren/
  README.md
  docs/
  pyproject.toml
  src/valren/
  tests/fixtures/
  config/interest-profile.yaml
  config/sources.yaml
  .env.example
  .gitignore
  docker-compose.yml
  data/                  # SQLite และ state; ไม่เก็บใน version control
  .hermes/               # ของ VARLEN เท่านั้น เมื่อถึงเฟส 3
```

## 4. แหล่งข้อมูลและความหมายของความใหม่

เอกสาร API ทางการได้รับการตรวจเมื่อวางแผน แต่ยังไม่ได้ทดสอบ endpoint ด้วย credentials หรือเครือข่าย production

**GitHub repo:** ใช้ REST Search แบ่งตาม topic และช่วงเวลา; แยก repo เพิ่งสร้างกับ repo เก่าที่เพิ่งได้รับความนิยม เก็บ snapshot stars เพื่อคำนวณการเติบโตหลังมีข้อมูลเพียงพอ วันแรกใช้ stars เป็นสัญญาณคร่าว ๆ และไม่เรียกว่า growth อย่าอ้างว่าผล Search คือ GitHub Trending อย่างเป็นทางการ Search มีเพดาน 1,000 ผลต่อ query และอาจคืน `incomplete_results`; ต้องแบ่ง query และรายงาน coverage ที่ขาด [GitHub Search](https://docs.github.com/en/rest/search/search)

**Open model LLM/CV:** ใช้ Hub API และ model card ตรวจ publisher, release date, license, modality และเงื่อนไข gated/commercial แยก open weights จาก open source ไม่สรุปว่าเปิด source เพียงเพราะอยู่บน Hub; `lastModified` ไม่ใช่วันเปิดตัวเสมอไป กรอง mirror/quantization ที่ไม่เพิ่มคุณค่าโดยใช้ metadata และความเกี่ยวข้อง ไม่ใช้ชื่อคล้ายกันอย่างเดียว [Hub API](https://huggingface.co/docs/hub/en/api), [HfApi](https://huggingface.co/docs/huggingface_hub/main/en/package_reference/hf_api)

**Paper:** เริ่ม arXiv `cs.AI`, `cs.LG`, `cs.CV`, `cs.CL` แล้วปรับตาม profile ใช้ submitted date สำหรับของใหม่ แยก revised date; query รายวัน cache และเว้นอย่างน้อย 3 วินาทีระหว่างคำขอต่อเนื่อง HF Daily Papers เป็นแหล่งเสริมภายหลัง เมื่อยืนยัน endpoint/เงื่อนไขแล้ว [arXiv API manual](https://info.arxiv.org/help/api/user-manual.html)

**Frontier LLM:** ใช้ allowlist ของ announcement/model documentation จากผู้พัฒนาโดยตรง เลือกค่ายตาม profile และยืนยัน feed/วิธีอ่านในเฟส 1 ถ้าไม่มี RSS ใช้หน้า changelog ที่กำหนดไว้ ตรวจชื่อรุ่น release event วันประกาศกับวันเปิดให้ใช้จริง และแยก preview/GA; benchmark จากผู้ขายต้องติดป้ายว่าเป็นคำกล่าวอ้างของผู้ขาย

ทุก connector มี pagination, timeout, response-size limit, retry ที่มีจำนวนครั้งจำกัดและ backoff/jitter เคารพ `Retry-After` และ quota header; source ใดล้มให้ source อื่นทำต่อ พร้อมรายงาน partial run ห้ามเปลี่ยน checkpoint ของ source ที่ยังเก็บไม่ครบโดยทำข้อมูลตกหล่น

## 5. ข้อมูล การเช็กซ้ำ และการกู้คืน

Notion เป็นแหล่งความจริงของความรู้และประวัติการแนะนำ SQLite เก็บ operational state เพิ่มเติม จึงไม่ใช่แค่ cache: candidates สร้างใหม่ได้ แต่ pending delivery และ usage ที่ยังไม่ sync ต้อง backup ด้วย

Canonical key มี namespace และสร้างด้วยโค้ด:

- Paper: `arxiv:<base-id>` ตัด version suffix เพื่อไม่แนะนำซ้ำเมื่อ v2 ออก แต่เก็บ version ที่อ่านไว้
- Repo: `github:<numeric-repository-id>` ใช้ `owner/repo` เป็นชื่อและ alias เพื่อรองรับ rename/transfer
- Model: `hf:<model-id>` เก็บ ID ตามต้นทางและ alias เมื่อยืนยันการย้าย/เปลี่ยนชื่อ ไม่ lowercase ทุก ID โดยเดา
- Frontier: `frontier:<publisher>:<stable-release-id>` ต้องมี mapping ที่ตรวจได้ ไม่ใช้ชื่อที่ LLM แต่ง

Paper, repo และ model ของงานเดียวกันยังเป็นคนละ entity เชื่อมด้วย related IDs; grouping ช่วยไม่ให้ digest วันเดียวกันมีข่าวงานเดียวซ้ำสามรายการ โดยไม่ลบข้อมูลต้นทาง

Schema ใช้ field ทั้งหมดในต้นฉบับ เพิ่ม `Published on`, `Discovered on`, `Verification status` และ provenance ใน page body เก็บเวลา fetch, URL และ section/page ที่รองรับข้อกล่าวอ้าง เนื้อหายาวของ Tutor ใช้ blocks; `Feedback` และ `My notes` เป็นของผู้ใช้ ห้าม writer เขียนทับ

แยก Library Status (`New`, `Recommended`, `Reading`, `Deep-dived`, `Skipped`) จาก processing/delivery state ใน SQLite สถานะใน Library ไม่ถอยหลังเมื่อ retry; `Recommended on` เก็บครั้งแรก; Tutor ที่ผู้ใช้ส่งมาตรง ๆ ไม่ต้องถูกนับว่าเคยอยู่ใน digest โดยอัตโนมัติ

ขั้นตอนป้องกันซ้ำและความเสียหาย:

1. ใช้ SQLite UNIQUE(canonical_key) และ lock ให้มี worker เขียนเพียงตัวเดียว พร้อมตรวจประวัติ Recommended ก่อนใช้ LLM
2. เก็บ `New` เป็น candidate ได้ ไม่ตัดทิ้งถาวรเพียงเพราะมีแถวแล้ว รายการ New ยังเข้ารอบคัดเลือกภายหลังได้
3. ก่อน create ใน Notion ค้น exact Canonical ID และ aliases ถ้าพบให้ผูก page ID; ถ้า create timeout ให้ reconcile ก่อน retry ไม่สร้างซ้ำทันที; ถ้าพบหลายแถวให้แจ้ง conflict
4. บันทึกรายการที่เลือกและ digest payload เป็น durable job; sync Notion เป็น Recommended ก่อนจึงเปิดให้ delivery ส่งได้
5. Outbox เก็บ key ตาม digest/date/channel, attempts และ remote receipt เมื่อมี ส่งสำเร็จแล้วไม่ส่งซ้ำจากการรัน scheduler รอบใหม่
6. หากปลายทางรับแล้วแต่ client timeout การส่งแบบ exactly-once รับประกันไม่ได้ โดยเฉพาะ webhook ให้ mark `uncertain` และ reconcile/ตรวจเองก่อน retry แทนการอ้างว่าป้องกันข้อความซ้ำได้ทุกกรณี
7. เมื่อ SQLite หาย ให้ import Library แบบ pagination ก่อนเปิด Radar แต่ระงับ delivery จนตรวจ pending/uncertain จาก backup แล้ว ประวัติ usage ใช้ provider report ประกอบ

Notion API ต้องระบุ `Notion-Version`; เอกสารที่ตรวจมีตัวอย่าง `2026-03-11` ให้ pin รุ่นที่ integration test ผ่าน และใช้ `data_source_id` สำหรับ query แยกจาก `database_id` [Versioning](https://developers.notion.com/reference/versioning), [Query data source](https://developers.notion.com/reference/query-a-data-source)

## 6. สิทธิ์และข้อมูลที่ไม่น่าเชื่อถือ

- ไม่อ่าน `.env`, `.hermes` หรือ credentials ของ Malren/Trevan; ไม่เปลี่ยน root Compose หรือเปิดสิทธิ์ agent อื่น
- Library writer integration แชร์เฉพาะ Library; Profile reader integration แยกและเปิดแค่อ่าน แชร์เฉพาะ Profile เพราะ content capabilities เป็นระดับ integration การแชร์สองหน้าให้ token ที่เขียนได้ตัวเดียวไม่บังคับ read-only Profile ได้ตามเจตนาเดิม นี่ทำให้จำนวน secrets มากกว่าสี่อย่างในข้อเสนอเดิม [Notion capabilities](https://developers.notion.com/reference/capabilities)
- ไม่แชร์ parent page ที่มีข้อมูลอื่น เพราะสิทธิ์สืบทอดไป children ใช้ negative test กับ fixture page ที่ผู้ใช้ทราบว่าไม่ได้แชร์; ผล search ว่างอย่างเดียวพิสูจน์ขอบเขตสิทธิ์ทั้งหมดไม่ได้
- จำกัด write target ด้วย data source/page membership; LLM เสนอเนื้อหาได้ แต่เลือก Notion page ปลายทาง, credential, channel หรือ URL สำหรับส่งข้อมูลเองไม่ได้
- Fetch เฉพาะ HTTP(S) ที่อนุญาต ป้องกัน localhost/private/link-local/metadata IP ทั้ง IPv4/IPv6 ตรวจ DNS และทุก redirect; ไม่เปิด local file ไม่ตาม URL ที่โมเดลแต่งโดยตรง
- README, HTML, PDF และข้อความจาก agent อื่นเป็นข้อมูล ไม่ใช่คำสั่ง แยกจาก system prompt; parser ไม่ execute embedded code; จำกัดขนาด จำนวนหน้า เวลา และ context
- ตรวจ structured output และ citation กับ source IDs ที่ fetch จริง ห้ามสร้าง benchmark ตัวเลข/ข้อสรุปที่ไม่มีหลักฐาน
- Telegram รับเฉพาะ user/chat ID ที่กำหนด; feedback ผูกกับ item และผู้ใช้จริง; agent_net default-deny งานที่ใช้เงินต้องมี user approval ที่ผูกกับคำขอและมีอายุ
- แยก environment/process ของ LLM จาก writer credentials เท่าที่ runtime รองรับ; model ไม่มี unrestricted tools และไม่เห็น secret ใน prompt/log
- Compose ภายใน `valren/` ใช้ non-root, จำกัด resources, drop capabilities, ไม่ mount Docker socket/host root; ประเมิน read-only filesystem กับ path ที่ Hermes ต้องเขียนจริงก่อนใช้

Verification เริ่มจากตรวจชื่อ/วันที่/license/claim กับ primary source ไม่ได้รัน benchmark หรือพิสูจน์ผลทดลองซ้ำ ใช้ `Unverified`, `Source-checked`, `Conflicting`; ระบุ self-reported results และขอบเขตที่อ่านได้ ถ้ามีแค่ abstract ต้องบอก ไม่สร้างบทเรียนเหมือนอ่าน full text แล้ว

## 7. งบ คุณภาพ และการดูแล

เก็บ token/cost ต่อ job และแยก Radar/Tutor ก่อนเรียก LLM reserve งบตาม input และ max output จาก pricing ที่ตรวจจริง แล้ว reconcile usage หลังตอบ รวม failed attempts; ป้องกันงานพร้อมกันใช้ budget ก้อนเดียวเกินเพดาน ถ้า usage ไม่ทราบให้ค้าง reservation ไว้ก่อน

แจ้งเมื่อใช้งบถึง 80%; เมื่อไม่พอให้หยุด LLM แต่ยัง fetch/cache ได้ แจ้งสถานะโดยไม่เรียก LLM เพิ่ม ราคาหรือโมเดลที่ไม่รู้จักให้ fail closed งานเกิน context ต้อง chunk แบบมี source anchors และจำกัดจำนวน chunk; ไม่ส่ง paper ยาวทั้งฉบับซ้ำโดยไม่มีเพดาน

Logs เป็น JSON ไม่มี secret/เนื้อหาส่วนตัว เก็บ run ID, source health, fetched/new/duplicate/selected counts, Notion errors, delivery state, tokens และ cost มี health ผ่าน last successful run และคิวค้าง; source เดียวเสียเตือนแบบรวมช่วงเวลาทำการ เหตุระบบหลักเสียจึงใช้ช่องทางฉุกเฉินตามที่ตั้งไว้

เพิ่ม backup ของ `valren/.hermes/` และ SQLite ด้วย snapshot ที่ consistent ผ่าน backup API รวม config ที่กู้คืนได้ ตรวจ restore จริงก่อน production การแก้ restic job กลางอยู่นอก directory ที่อนุญาต จึงจัดทำคำแนะนำภายใน valren ให้ผู้ดูแลนำไปใช้ ไม่มีการแก้ job กลางในงานนี้

## 8. ลำดับส่งมอบและเกณฑ์ผ่าน

### เฟส 0 — Contract และโครงที่รัน offline ได้

สร้าง package/CLI/config validation, fixtures และ `.env.example` ที่ไม่มี secret กำหนด Library schema และแบบร่าง Profile ตรวจ Notion API contract และ interface Hermes จากรุ่นที่มีจริงก่อนผูกใช้งาน

เกณฑ์ผ่าน: CLI dry-run ใช้ fixture ได้โดยไม่ใช้ credentials; invalid config ถูกปฏิเสธ; เมื่อมี integration ของ VARLEN จึงทดสอบสร้าง/อ่าน/อัปเดตแถวทดสอบและตรวจสิทธิ์ Profile/negative fixture จากนั้นวัด RAM จริงก่อนเพิ่ม container โดยไม่ถือค่า 6.7 GiB ในเอกสารเก่าว่ายังใช้ได้

### เฟส 1 — Radar ที่ไม่ใช้ LLM

สร้าง connectors ครบทั้งสี่กลุ่ม, normalization, deduplication, SQLite, Notion New writer และ sync-library เริ่ม connector ทีละตัวด้วย fixtures แล้วทดสอบ live แบบจำกัดปริมาณ

เกณฑ์ผ่าน: แหล่งที่เปิดใช้ดึงจริงได้; รันข้อมูลเดิมสองครั้งไม่เพิ่มแถวซ้ำ; rename, arXiv version, pagination, rate limit, source ล้มและ Notion timeout มีผลตามที่ออกแบบ; รันจริงต่อเนื่องอย่างน้อย 3 วัน ไม่มีแถวซ้ำที่ตรวจพบและไม่ซ่อน source failures

### เฟส 2 — LLM และ daily digest: MVP ใช้งานจริง

เพิ่ม relevance ตาม Profile, สรุปไทยพร้อมหลักฐาน, verification, budget reservation, outbox และ Discord webhook จำกัด candidate และรายการตามเพดาน เริ่ม preview digest ในเครื่องก่อนเปิดส่งจริง

เกณฑ์ผ่านทางเทคนิค: source injection เปลี่ยนสิทธิ์ไม่ได้; ไม่เขียนทับ My notes/Feedback; งบและ quiet hours บังคับใช้รวม retry; crash ระหว่าง write/send กู้คืนได้; dry-run ไม่เขียน Notion/ส่งข้อความ/เรียก LLM แบบเสียเงิน

เกณฑ์คุณภาพที่เสนอ: ทดลองอ่าน 7 วัน ผู้ใช้ให้ feedback อย่างน้อย 10 รายการ; อย่างน้อย 70% ระบุว่าน่าอ่าน และตรวจตัวอย่างแล้วทุกข้อกล่าวอ้างสำคัญมีแหล่งรองรับ ผู้ใช้ปรับเกณฑ์นี้ได้ก่อนเริ่ม pilot ถ้าไม่ผ่านปรับ Profile/แหล่งข้อมูลก่อนเพิ่มความซับซ้อน

### เฟส 3 — Hermes และ Tutor ผ่าน Telegram

สร้าง `.hermes` และ bot ของตัวเอง เชื่อม worker ผ่าน tool ที่จำกัดสิทธิ์ บทเรียนเรียงภาพรวม → ศัพท์ → ปัญหา/วิธี/ผล/ข้อจำกัด → ความเกี่ยวข้องกับงาน → แหล่งอ้างอิง แล้ว persist จึงเปลี่ยน Status เป็น Deep-dived

เกณฑ์ผ่าน: สอนได้ทั้ง paper ใหม่และเก่า; URL ไม่อนุญาตถูกปฏิเสธ; อ่าน full text ไม่ได้ต้องเปิดเผย; user/chat อื่นสั่งไม่ได้; retry ไม่เพิ่มบทเรียนชุดเดิมซ้ำและไม่เปลี่ยนเป็น Deep-dived ก่อนบันทึกครบ; container restart แล้ว state ยังอยู่

### เฟส 4 — Feedback และ agent_net

เริ่มใช้ Feedback ใน Library ก่อนปุ่มกด ทำ taste summary ไม่เกิน 1–2 blocks; ปุ่มเป็นช่องทางเสริมภายหลัง Malren อ่านผ่าน credential ที่แยก ไม่รับ writer token ของ VARLEN และไม่แก้ config ของ Malren ในงานนี้

เกณฑ์ผ่าน: fixture Disliked ลดคะแนนหัวข้อที่เกี่ยวข้องโดยไม่ทำให้หัวข้อทั้งหมดหาย; ข้อความจาก agent อื่นเปิดงานมีค่าใช้จ่ายไม่ได้จนผู้ใช้อนุมัติคำขอนั้น; คำขอเขียนไฟล์/เปลี่ยน config/แก้สถานะแทนผู้ใช้ถูกปฏิเสธ

### ก่อนเปิดใช้งานต่อเนื่อง

ทดสอบ restore, budget exhaustion, credential หมดอายุ, source ล่ม, restart กลางงาน และ stale locks วัด RAM สูงสุดใน Radar/Tutor ให้เหลือ headroom ตามเครื่องจริง เก็บหลักฐานใน `docs/validation.md` เมื่อทดสอบแล้ว ไม่กรอกผลผ่านล่วงหน้า แต่ละเฟสจบด้วยผลตรวจให้ผู้ใช้พิจารณาก่อนขยายเฟสตามแนวทางในเอกสารต้นทาง

## 9. จุดเริ่มลงมือและข้อมูลที่ต้องมีภายหลัง

เริ่ม implementation ครั้งแรกด้วย CLI dry-run + canonical IDs + SQLite และ connector arXiv แบบ fixture เพราะพิสูจน์วงจร fetch/dedup ได้โดยไม่ต้องมี secrets จากนั้นเพิ่ม connector อื่นและ Notion writer ตามเฟส 1

ก่อน live Notion ต้องมี Library/Profile IDs และ integration ที่แยกสิทธิ์ ก่อนเฟส 2 ต้องมี Profile ที่ผู้ใช้แก้แล้ว, งบรายเดือน, provider/model และ Discord channel/webhook ก่อนเฟส 3 ต้องมี Hermes version/interface, persona, Telegram user/chat IDs และผลวัด RAM

Secrets ให้รับผ่านช่องทางส่วนตัวหรือใส่ `.env` บนเครื่องโดยตรงตามเครื่องมือที่มี ห้ามวางในเอกสาร แชต log หรือ commit แผนนี้ยังไม่สร้างบัญชี Notion database, bot, schedule หรือ container จริง
