# Landing page content: Prototype Kit

The copy of the live landing page (`site/index.html`, version 0.12.8), section by section, in English and Vietnamese.
English is the HTML source; Vietnamese comes from the page's language dictionary and shows when a visitor picks **VI** (or the browser language is Vietnamese).

Rules for the copy: every claim comes from the repository or from a real test run of the kit. No invented statistics, star counts, logos or testimonials.
Product names, skill names, file names and commands stay in English in both languages.
Style: one idea per sentence, headlines of eight words or fewer, at most two short sentences per card, step or FAQ answer; each point is made once, in the section where it fits best.

Notes in *[brackets and italics]* describe layout, not page text.

---

## 0. Page meta
- **Title**
  - EN: Prototype Kit: Claude Code skills from idea to design handoff
  - VI: Prototype Kit: Bộ skill Claude Code từ ý tưởng đến bàn giao thiết kế
- **Description**
  - EN: 18 Claude Code skills that take a design from requirement to a checked handoff, with any design system. People decide; the kit checks.
  - VI: 18 skill Claude Code đưa thiết kế từ yêu cầu đến bàn giao đã kiểm tra, với mọi design system. Người quyết định, kit kiểm tra.
- **Favicon and logo:** layered-tiles icon (`favicon.ico`, `assets/favicon-48.png`, `assets/apple-touch-icon.png`, `assets/logo.webp`).

## 1. Header

*[Floating glass pill, sticky. Left: logo + "Prototype Kit". Centre: links. Right: EN/VI switch, light/dark toggle, Install button. Under 480 px the Install button hides; under 390 px only the logo icon stays.]*

- **Link**
  - EN: Features
  - VI: Tính năng
- **Link**
  - EN: Process
  - VI: Quy trình
- **Link**
  - EN: Console
  - VI: Console
- **Link**
  - EN: Skills
  - VI: Skill
- **Link**
  - EN: FAQ
  - VI: Hỏi đáp
- **Button**
  - EN: Install
  - VI: Cài đặt

## 2. Hero

- **Heading**
  - EN: From idea to developer handoff, with your design system.
  - VI: Từ ý tưởng đến bàn giao cho developer, với design system của bạn.
- **Lede**
  - EN: Prototype Kit is a free Claude Code plugin with 18 skills. It takes a requirement to a checked prototype, a spec and one handoff package. People decide; the kit checks.
  - VI: Prototype Kit là plugin Claude Code miễn phí gồm 18 skill. Kit đưa một yêu cầu thành prototype đã kiểm tra, spec và một gói bàn giao. Người quyết định, kit kiểm tra.
- **Primary button (→ #install)**
  - EN: Install the kit
  - VI: Cài đặt kit
- **Secondary button (→ #skills)**
  - EN: Browse the skills
  - VI: Xem các skill

## 3. What the kit does
- **Section heading**
  - EN: What the kit does
  - VI: Kit làm được gì

### 3.1 Skill flow (full-width card)

*[Diagram built in HTML/CSS. Top bar: `brief`. Six numbered stages joined by arrows, each with its skills (duotone icons) and its output. Then an "After development" bar and the design system loop. Stacks vertically under 1100 px.]*

- **Eyebrow**
  - EN: Skill flow
  - VI: Luồng skill
- **Heading**
  - EN: How the 18 skills connect
  - VI: 18 skill nối với nhau thế nào
- **Text**
  - EN: Start anywhere with `brief`. Each step hands its output to the next.
  - VI: Bắt đầu ở đâu cũng được với `brief`. Mỗi bước chuyển kết quả cho bước sau.
- **Entry bar**
  - EN: `brief` routes your request to the right step
  - VI: `brief` chuyển yêu cầu của bạn tới đúng bước

| # | Stage (EN / VI) | Skills | Output (EN / VI) |
|---|---|---|---|
| 1 | Set up / Dựng dự án | `adopt` (if no DS / nếu chưa có DS), `kickoff`, `context` | `kit.config.json`, product memory / `kit.config.json`, bộ nhớ sản phẩm |
| 2 | Define / Xác định | `define` | Questions, waves, traceability / Câu hỏi, các đợt, truy vết |
| 3 | Explore / Khám phá | `explore` | One chosen direction / Một hướng đã chọn |
| 4 | Build / Dựng | `prototype`, `validate` | Screens checked in the browser / Màn hình đã kiểm tra trên trình duyệt |
| 5 | Specify / Đặc tả | `annotate`, `wireflow`, `mockup` | Spec, Figma flow board / Spec, board luồng Figma |
| 6 | Hand off / Bàn giao | `handoff`, `share` | One zip, email draft / Một file zip, email nháp |

- **After development bar**
  - EN: After development: `verify` checks the developers' build against the approved design
  - VI: Sau khi phát triển: `verify` so bản developer làm với thiết kế đã duyệt
- **Design system loop bar**
  - EN: Design system loop: `review` → `sync` → `contribute` → `document`, feeds back into Set up and Build
  - VI: Vòng design system: `review` → `sync` → `contribute` → `document`, quay lại bước Dựng dự án và Dựng

### 3.2 Any design system (wide card)

*[Visual: `kit.config.json` → `ds/acme/ds.json` (highlighted) → chip.]*

- **Eyebrow**
  - EN: Any design system
  - VI: Mọi design system
- **Heading**
  - EN: Two files connect your design system
  - VI: Hai file nối kit với design system
- **Text**
  - EN: `kit.config.json` sets the language, stack and apps. A `ds.json` profile sets tokens, CSS, theming and Figma libraries.
  - VI: `kit.config.json` đặt ngôn ngữ, stack và các app. Profile `ds.json` đặt token, CSS, theming và thư viện Figma.
- **Chip**
  - EN: 18 skills
  - VI: 18 skill

### 3.3 Contrast check (narrow card)

*[Big number and two small stats from the real test run (148 pairs checked, 11 pass after adjustment).]*

- **Eyebrow**
  - EN: Contrast check
  - VI: Kiểm tra tương phản
- **Heading**
  - EN: Every colour pair, light and dark
  - VI: Mọi cặp màu, cả sáng lẫn tối
- **Text**
  - EN: Text needs 4.5:1, icons and borders 3:1. Thresholds never drop.
  - VI: Chữ cần 4.5:1, icon và viền cần 3:1. Ngưỡng không bao giờ bị hạ.
- **Big number**
  - EN: 0 fail
  - VI: 0 lỗi
- **Big number label**
  - EN: In our test run
  - VI: Trong lần chạy thử
- **Stat 1 label**
  - EN: Pairs checked
  - VI: Cặp màu đã kiểm
- **Stat 2 label**
  - EN: Pass after adjustment
  - VI: Đạt sau khi chỉnh

### 3.4 No design system yet (narrow card)

*[Big number (~30) and two small stats (48 px, 3).]*

- **Eyebrow**
  - EN: No design system yet
  - VI: Chưa có design system
- **Heading**
  - EN: Start from a preset
  - VI: Bắt đầu từ một preset
- **Text**
  - EN: `adopt` builds one from shadcn or atelier, with your brand colour, radius and font.
  - VI: `adopt` dựng một bộ từ shadcn hoặc atelier, theo màu thương hiệu, độ bo góc và font của bạn.
- **Big number label**
  - EN: Components
  - VI: Component
- **Stat 1 label**
  - EN: Touch targets
  - VI: Vùng chạm
- **Stat 2 label**
  - EN: Platforms
  - VI: Nền tảng

### 3.5 Handoff package (wide card)

*[Code block: the real package layout from `skills/handoff/scripts/pkg.py` (AGENTS.md, README.md, requirements/ with checklist-feature.csv, checklist-qc.csv, changelog.md, spec/, prototype/). `pkg.py smoke` is new in 0.11.0.]*

- **Eyebrow**
  - EN: Handoff package
  - VI: Gói bàn giao
- **Heading**
  - EN: One zip, a reading path per role
  - VI: Một file zip, mỗi vai trò một lối đọc
- **Text**
  - EN: BA gets the spec, QC a checklist, developers `AGENTS.md` and the prototype. `pkg.py smoke` test-opens the unpacked zip before you send it.
  - VI: BA nhận spec, QC nhận checklist, developer nhận `AGENTS.md` và prototype. `pkg.py smoke` mở thử gói đã giải nén trước khi bạn gửi.
- **Code comment**
  - EN: // layout of a handoff package
  - VI: // cấu trúc một gói bàn giao
- **Code comment**
  - EN: reading paths for BA, QC, developers
  - VI: lối đọc cho BA, QC, developer
- **Code comment**
  - EN: one Markdown file per unit
  - VI: mỗi unit một file Markdown

### 3.6 People decide (half card)

*[Status chips joined by arrows, "Approved" highlighted; gates line under it.]*

- **Eyebrow**
  - EN: People decide
  - VI: Người quyết định
- **Heading**
  - EN: Every decision has an owner
  - VI: Quyết định nào cũng có người chịu trách nhiệm
- **Text**
  - EN: The kit proposes; a named person approves. Each decision is tracked until the build is verified.
  - VI: Kit đề xuất, một người được nêu tên duyệt. Mỗi quyết định được theo dõi đến khi bản dựng được kiểm chứng.
- **Status 1**
  - EN: Observed
  - VI: Quan sát
- **Status 2**
  - EN: Proposed
  - VI: Đề xuất
- **Status 3 (highlighted)**
  - EN: Approved
  - VI: Đã duyệt
- **Status 4**
  - EN: Implemented
  - VI: Đã dựng
- **Status 5**
  - EN: Verified
  - VI: Đã kiểm chứng
- **Gates line**
  - EN: Gates: plan · design direction · new component · new page · DS proposal · accepted deviation
  - VI: Các bước duyệt: kế hoạch · hướng thiết kế · component mới · trang mới · đề xuất vào DS · chấp nhận sai lệch

### 3.7 Checked, not just generated (half card)

*[Mini report table: Fail 0 · Needs a human 3 · Skipped 0 (illustration of the validate report). Waivers and new/carried-over marks are from 0.11.0.]*

- **Eyebrow**
  - EN: Checked, not just generated
  - VI: Được kiểm chứng, không chỉ được sinh ra
- **Heading**
  - EN: One report separates failures from judgement calls
  - VI: Một báo cáo tách lỗi khỏi việc cần người xét
- **Text**
  - EN: `validate` runs every screen, state and flow at three widths, light and dark. Known findings are waived with a reason; each is marked new or carried over.
  - VI: `validate` chạy mọi màn hình, trạng thái và luồng ở ba kích thước, cả sáng lẫn tối. Lỗi đã biết được miễn kèm lý do; mỗi lỗi ghi rõ là mới hay có từ lần trước.
- **Row 1**
  - EN: Fail
  - VI: Lỗi
- **Row 1 detail**
  - EN: errors, overflow, serious a11y, broken flows
  - VI: lỗi trang, tràn ngang, a11y nghiêm trọng, luồng hỏng
- **Row 2**
  - EN: Needs a human
  - VI: Cần người xem
- **Row 2 detail**
  - EN: touch targets, focus, visual changes
  - VI: vùng chạm, focus, thay đổi hình ảnh
- **Row 3**
  - EN: Skipped
  - VI: Bỏ qua
- **Row 3 detail**
  - EN: always with a reason, never as passed
  - VI: luôn kèm lý do, không tính là đạt

## 4. How the kit works

*[Seven numbered steps on a vertical line, inside a card. Each step: duotone icon, title, text, skill chips.]*

- **Eyebrow**
  - EN: Workflow
  - VI: Quy trình
- **Heading**
  - EN: How the kit works
  - VI: Kit hoạt động thế nào
- **Intro**
  - EN: Seven steps. Each one is a skill you can also run alone.
  - VI: Bảy bước. Bước nào cũng là một skill chạy riêng được.

### Step 1 · Set up the project / Dựng dự án

- EN: Pick the language, stack and design system. `context` keeps users, rules and decisions.
- VI: Chọn ngôn ngữ, stack và design system. `context` giữ người dùng, luật và quyết định.
- Skills: `adopt` `kickoff` `context`

### Step 2 · Define the work / Xác định phạm vi

- EN: Requirements become questions, delivery waves and a traceability matrix. Porting a live page? `extract_rules.py` drafts a parity checklist.
- VI: Yêu cầu được tách thành câu hỏi, các đợt bàn giao và ma trận truy vết. Chuyển một trang đang chạy? `extract_rules.py` soạn sẵn checklist đối chiếu.
- Skills: `define`

### Step 3 · Explore directions / Khám phá các hướng

- EN: Two to four directions, side by side. A person picks one, and the reason is kept.
- VI: Hai đến bốn hướng, đặt cạnh nhau. Người chọn một hướng, lý do được lưu lại.
- Skills: `explore`

### Step 4 · Build and check / Dựng và kiểm tra

- EN: Screens use DS components; the kit asks before adding new ones. Built-in checklists cover accessibility, states, edge data, motion and heuristics.
- VI: Màn hình dùng component của DS; kit hỏi trước khi thêm cái mới. Có sẵn checklist cho accessibility, trạng thái, dữ liệu biên, chuyển động và heuristic.
- Skills: `prototype` `validate`

### Step 5 · Write the spec / Viết spec

- EN: Screen captures with pins and token names, plus a Figma flow board. A new round updates the board in place.
- VI: Ảnh chụp màn hình có ghim và tên token, kèm board luồng trên Figma. Vòng sau cập nhật board tại chỗ.
- Skills: `annotate` `wireflow` `mockup`

### Step 6 · Hand off / Bàn giao

- EN: One zip and an email draft; the kit never sends it. No Figma links yet? Package as `awaiting-figma`, then `relink`.
- VI: Một file zip và email nháp; kit không bao giờ tự gửi. Chưa có link Figma? Đóng gói với trạng thái `awaiting-figma`, rồi `relink`.
- Skills: `handoff` `share`

### Step 7 · Verify the build / Kiểm chứng bản dựng

- EN: Compare the developers' build with the approved prototype. Each difference is a defect or an approved deviation.
- VI: So bản developer làm với prototype đã duyệt. Mỗi khác biệt là lỗi hoặc sai lệch đã duyệt.
- Skills: `verify`

## 5. A real run

*[Terminal-style console with three tabs. The `//` comment lines are translated; the command output is the real output of a test run and stays in English.]*

- **Heading**
  - EN: A real run
  - VI: Một lần chạy thật
- **Intro**
  - EN: Setting up a React project. Trimmed; numbers unchanged.
  - VI: Dựng một dự án React. Đã rút gọn, số liệu giữ nguyên.
- **Tabs**
  - EN: 1. Adopt · 2. Kickoff · 3. Build and audit
  - VI: 1. Adopt · 2. Kickoff · 3. Build và audit
- **Output (unchanged, trimmed):** `adopt.py` → "Contrast: 148 pairs · 137 pass · 11 pass after tone adjustment · 0 fail", "Profile OK"; `scaffold.py` → "Created apps/nnminh-web (react, spa) from templates/react: 23 file(s)."; `npm run build` → "dist/index.html 423.97 kB │ gzip: 123.30 kB"; `audit_app.py` → hard-coded colours, Tailwind arbitrary values and DS component use all Pass.

## 6. The 18 skills

*[Skills browser: index on the left (vertical list on desktop; one scrolling row of chips under 800 px), detail panel on the right with group, large duotone icon, name, description, `/kit:<name>` and a link to SKILL.md on GitHub.]*

- **Heading**
  - EN: The 18 skills
  - VI: 18 skill
- **Intro**
  - EN: Pick one to see what it does.
  - VI: Chọn một skill để xem nó làm gì.
- **Index label**
  - EN: Skills index
  - VI: Danh sách skill
- **Link**
  - EN: Read SKILL.md on GitHub
  - VI: Đọc SKILL.md trên GitHub

| # | Skill | Group (EN / VI) | Description (EN) | Description (VI) |
|---|---|---|---|---|
| 1 | `brief` | Start / Bắt đầu | Reads a plain-language request and routes it to the right skill with a one-line plan. Start here when unsure. | Đọc yêu cầu viết bằng lời thường và chuyển tới đúng skill, kèm kế hoạch một dòng. Chưa biết bắt đầu từ đâu thì dùng skill này. |
| 2 | `kickoff` | Start / Bắt đầu | Sets up a project: language, stack, design system and the first app. It links the DS profile and runs a smoke test. | Dựng dự án: ngôn ngữ, stack, design system và app đầu tiên. Skill liên kết profile DS rồi chạy smoke test. |
| 3 | `adopt` | Start / Bắt đầu | Builds a base design system from the shadcn or atelier preset, structured on Material Design 3. Every colour pair is checked for contrast. | Dựng design system nền từ preset shadcn hoặc atelier, cấu trúc theo Material Design 3. Mọi cặp màu đều được kiểm tra tương phản. |
| 4 | `context` | Plan and build / Lên kế hoạch và dựng | Keeps the product memory other skills read: personas, UX principles, business rules and a decision log with owners. | Giữ bộ nhớ sản phẩm cho các skill khác đọc: persona, nguyên tắc UX, luật nghiệp vụ và nhật ký quyết định kèm người quyết định. |
| 5 | `define` | Plan and build / Lên kế hoạch và dựng | Turns requirements into units, open questions and delivery waves with acceptance criteria. For an existing page, it drafts a parity checklist. | Tách yêu cầu thành unit, câu hỏi mở và các đợt bàn giao có tiêu chí nghiệm thu. Với trang đã có, skill soạn sẵn checklist đối chiếu. |
| 6 | `explore` | Plan and build / Lên kế hoạch và dựng | Builds two to four distinct directions for one design question and records the one a person picks. Prototypes start only from a chosen direction. | Dựng hai đến bốn hướng khác hẳn nhau cho một câu hỏi thiết kế và ghi lại hướng người chọn. Prototype chỉ dựng từ hướng đã chọn. |
| 7 | `prototype` | Plan and build / Lên kế hoạch và dựng | Builds screens and flows from a request, a plan wave or screenshots, mapped to the DS catalogue. It asks before any new component or page. | Dựng màn hình và luồng từ yêu cầu, một đợt trong kế hoạch hoặc ảnh chụp, ánh xạ sang catalogue của DS. Skill hỏi trước khi tạo component hay trang mới. |
| 8 | `validate` | Quality / Chất lượng | Checks a prototype in the browser at phone, tablet and desktop widths, light and dark. One report separates failures, items for a human and waived findings. | Kiểm tra prototype trên trình duyệt ở cỡ điện thoại, máy tính bảng và máy tính, cả sáng lẫn tối. Một báo cáo tách riêng lỗi, điểm cần người xem và lỗi đã miễn. |
| 9 | `annotate` | Specify / Đặc tả | Writes the spec: one Markdown file per unit, every screen captured, elements pinned with token names and flows drawn as a wireflow. | Viết spec: mỗi unit một file Markdown, chụp đủ màn hình, ghim phần tử kèm tên token và vẽ luồng dạng wireflow. |
| 10 | `wireflow` | Specify / Đặc tả | Puts the flow on a Figma board, one screenshot per screen joined by arrows. Later rounds add screens and relabel arrows in place, so shared links keep working. | Đưa luồng lên board Figma, mỗi màn hình một ảnh, nối bằng mũi tên. Vòng sau thêm màn hình và đổi nhãn mũi tên tại chỗ, nên link đã chia sẻ vẫn dùng được. |
| 11 | `mockup` | Specify / Đặc tả | Rebuilds each screen on Figma as editable layers with auto layout, DS components and variables. An automatic check must pass. | Dựng lại từng màn hình trên Figma thành layer sửa được, có auto layout, component và biến của DS. Phải qua bước kiểm tra tự động. |
| 12 | `handoff` | Deliver / Bàn giao | Packs one zip for BA, QC and developers, with reading paths in AGENTS.md. pkg.py smoke opens the unpacked package in a browser. | Đóng gói một file zip cho BA, QC và developer, có lối đọc trong AGENTS.md. pkg.py smoke mở thử gói đã giải nén trên trình duyệt. |
| 13 | `share` | Deliver / Bàn giao | Drafts the handoff email with the Figma link, key changes and the zip attached. It only drafts; you send. | Soạn email bàn giao có link Figma, các thay đổi chính và file zip đính kèm. Skill chỉ soạn nháp, bạn tự gửi. |
| 14 | `verify` | Quality / Chất lượng | Compares the developers' build with the approved prototype: screens, tokens, components, texts, flows and accessibility. Each difference is a defect or an approved deviation. | So bản developer làm với prototype đã duyệt: màn hình, token, component, chữ, luồng và accessibility. Mỗi khác biệt là lỗi hoặc sai lệch đã duyệt. |
| 15 | `review` | Design system / Design system | A read-only audit of how well an app follows the DS: version, tokens, hard-coded values, component use and overrides. Each deviation comes with fix options. | Audit chỉ đọc, đo mức app tuân theo DS: phiên bản, token, giá trị gắn cứng, cách dùng component và chỗ ghi đè. Mỗi sai lệch kèm phương án sửa. |
| 16 | `sync` | Design system / Design system | Brings a new DS version into your apps. It asks before touching local components, then tests and records the change. | Đưa phiên bản DS mới vào các app. Skill hỏi trước khi đụng tới component local, rồi test và ghi lại thay đổi. |
| 17 | `contribute` | Design system / Design system | Keeps the local-component registry in step and proposes the best ones to the DS through two approval gates. | Giữ danh sách component local khớp với app và đề xuất những cái tốt vào DS qua hai bước duyệt. |
| 18 | `document` | Design system / Design system | Maintains the DS profile and docs: tokens and components at the source, the bundle, version, changelog and contrast. | Duy trì profile DS và tài liệu: token và component tại nguồn, bundle, phiên bản, changelog và tương phản. |

## 7. Install

*[Centred card with a soft gold glow. Command box with a Copy button, then a gold GitHub button.]*

- **Version pill**
  - EN: Version 0.12.8 · MIT licence
  - VI: Phiên bản 0.12.8 · Giấy phép MIT
- **Heading**
  - EN: Ready to prototype with your design system?
  - VI: Sẵn sàng dựng prototype với design system của bạn?
- **Text**
  - EN: Run these in Claude Code, then call `/kit:<skill>`.
  - VI: Chạy các lệnh sau trong Claude Code, rồi gọi `/kit:<skill>`.
- **Commands (same in both languages):**

  ```
  /plugin marketplace add MinhNhat0201/nnminh-prototype-kit
  /plugin install kit@nnminh-prototype-kit
  ```

- **Button (→ GitHub)**
  - EN: View on GitHub
  - VI: Xem trên GitHub

## 8. FAQ

*[Accordion in a card. Questions in page order. Questions that only repeated earlier sections (what the kit is, who decides, how validate works, checking the developers' build, whether a DS is needed first) were removed in 0.11.0.]*

- **Heading**
  - EN: Frequently asked questions
  - VI: Câu hỏi thường gặp

### Is it free?

- VI question: Có miễn phí không?
- EN: Yes, under the MIT licence. Both presets are MIT too: shadcn derives from shadcn/ui and shadcn-vue, atelier from the author's own design system.
- VI: Có, theo giấy phép MIT. Hai preset cũng theo MIT: shadcn dựng từ shadcn/ui và shadcn-vue, atelier từ design system riêng của tác giả.

### Which stacks does it support?

- VI question: Kit hỗ trợ những stack nào?
- EN: HTML (the default), React and Vue. Each app picks its own, so they can share one repository.
- VI: HTML (mặc định), React và Vue. Mỗi app chọn stack riêng, nên có thể chung một repo.

### Does it publish anything on its own?

- VI question: Kit có tự đăng gì không?
- EN: No. Skills save files and never commit, push or publish unless you ask.
- VI: Không. Skill chỉ lưu file, không commit, push hay đăng gì trừ khi bạn yêu cầu.

### Do I need Figma?

- VI question: Có cần Figma không?
- EN: Only for `wireflow`, `mockup` and one optional `adopt` step. Everything else works without it.
- VI: Chỉ cho `wireflow`, `mockup` và một bước tuỳ chọn của `adopt`. Mọi thứ khác chạy được mà không cần Figma.

### Which languages can the documents be in?

- VI question: Tài liệu sinh ra có thể viết bằng ngôn ngữ nào?
- EN: English and Vietnamese ship with the kit, set in `kit.config.json > language`. To add one, copy `locales/en/` and translate it.
- VI: Kit có sẵn tiếng Anh và tiếng Việt, đặt trong `kit.config.json > language`. Muốn thêm ngôn ngữ, sao chép `locales/en/` rồi dịch.

### What do I need installed?

- VI question: Cần cài những gì?
- EN: Claude Code, Python 3.9+, Node 18+, Playwright with Chromium, and Pillow.
- VI: Claude Code, Python 3.9+, Node 18+, Playwright kèm Chromium, và Pillow.

## 9. Footer

*[Four columns: about, Kit links (same labels as the header), Docs links, Project links. Base line with the version.]*

- **About**
  - EN: Claude Code skills for prototypes and design handoff.
  - VI: Skill Claude Code cho prototype và bàn giao thiết kế.
- **Copyright**
  - EN: © 2026 Prototype Kit by nnminh. MIT licence.
  - VI: © 2026 Prototype Kit bởi nnminh. Giấy phép MIT.
- **Column heading**
  - EN: Docs
  - VI: Tài liệu
- **Docs link**
  - EN: Configuration
  - VI: Cấu hình
- **Docs link**
  - EN: Stacks
  - VI: Stack
- **Docs link**
  - EN: Authoring
  - VI: Viết skill
- **Docs link**
  - EN: Changelog
  - VI: Nhật ký thay đổi
- **Column heading**
  - EN: Project
  - VI: Dự án
- **Project links:** GitHub (same in both), Licence / Giấy phép, shadcn notice / Ghi chú shadcn
- **Base line**
  - EN: Contributions welcome.
  - VI: Hoan nghênh đóng góp.
- **Version:** v0.12.8
