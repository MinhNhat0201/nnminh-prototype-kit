# Landing page content: Prototype Kit

The copy of the live landing page (`site/index.html`, version 0.6.0), section by section, in English and Vietnamese.
English is the HTML source; Vietnamese comes from the page's language dictionary and shows when a visitor picks **VI** (or the browser language is Vietnamese).

Rules for the copy: every claim comes from the repository or from a real test run of the kit. No invented statistics, star counts, logos or testimonials.
Product names, skill names, file names and commands stay in English in both languages.

Notes in *[brackets and italics]* describe layout, not page text.

---

## 0. Page meta
- **Title**
  - EN: Prototype Kit: Claude Code skills from idea to design handoff
  - VI: Prototype Kit: Bộ skill Claude Code từ ý tưởng đến bàn giao thiết kế
- **Description**
  - EN: A design workflow of 18 Claude Code skills, with any design system: plan, explore directions, prototype in HTML, React or Vue, check in the browser, spec, Figma flows, one handoff package, and a check of the developers' build. People decide at every gate.
  - VI: Quy trình thiết kế gồm 18 skill Claude Code, dùng với mọi design system: lên kế hoạch, khám phá hướng thiết kế, dựng prototype, kiểm tra trên trình duyệt, spec, luồng Figma, gói bàn giao và kiểm tra bản developer làm. Người quyết định ở mọi bước duyệt.
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

*[Centred. Display headline, second line in a gradient. Gold primary button, glass secondary button. Background: gold rays image (light) or gold rays on black with a warm glow (dark), at 30 % opacity.]*

- **Headline**
  - EN: From idea to developer handoff, with your design system.
  - VI: Từ ý tưởng đến bàn giao cho developer, với design system của bạn.
- **Lede**
  - EN: Prototype Kit is a free design workflow of 18 Claude Code skills. It plans the work, explores directions, builds HTML, React or Vue prototypes with your design system, checks them in the browser, writes the spec, puts the flows on Figma, packages everything for BA, QC and developers, then checks the developers' build against what was approved.
  - VI: Prototype Kit là quy trình thiết kế miễn phí gồm 18 skill cho Claude Code. Kit lên kế hoạch, khám phá các hướng thiết kế, dựng prototype HTML, React hoặc Vue bằng design system của bạn, kiểm tra trên trình duyệt, viết spec, đưa luồng lên Figma, đóng gói cho BA, QC và developer, rồi kiểm tra bản developer làm so với bản đã duyệt.
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
- **Intro**
  - EN: Design-system-aware skills for every step between a requirement and a handoff.
  - VI: Các skill hiểu design system của bạn, cho mọi bước từ yêu cầu đến bàn giao.

### 3.1 Skill flow (full-width card)

*[Diagram built in HTML/CSS. Top bar: `brief`. Six numbered stages joined by arrows, each with its skills (duotone icons) and its output. Then an "After development" bar and the design system loop. Stacks vertically under 1100 px.]*

- **Eyebrow**
  - EN: Skill flow
  - VI: Luồng skill
- **Heading**
  - EN: How the 18 skills connect
  - VI: 18 skill nối với nhau thế nào
- **Text**
  - EN: Start anywhere with `brief`. Each step hands its output to the next. A person decides at every gate; `context` remembers who decided what and why.
  - VI: Bắt đầu ở bất kỳ đâu với `brief`. Mỗi bước chuyển kết quả cho bước sau. Người quyết định ở mọi bước duyệt; `context` ghi nhớ ai đã quyết định gì và vì sao.
- **Entry bar**
  - EN: `brief` reads your request and sends it to the right step
  - VI: `brief` đọc yêu cầu của bạn và chuyển tới đúng bước

| # | Stage (EN / VI) | Skills | Output (EN / VI) |
|---|---|---|---|
| 1 | Set up / Dựng dự án | `adopt` (if no DS / nếu chưa có DS), `kickoff`, `context` | `kit.config.json`, product memory / `kit.config.json`, bộ nhớ sản phẩm |
| 2 | Define / Xác định | `define` | Questions, waves, traceability / Câu hỏi, các đợt, truy vết |
| 3 | Explore / Khám phá | `explore` | One direction, chosen by a person / Một hướng, do người chọn |
| 4 | Build / Dựng | `prototype`, `validate` | Screens checked in the browser / Màn hình đã kiểm tra trên trình duyệt |
| 5 | Specify / Đặc tả | `annotate`, `wireflow`, `mockup` | Spec, Figma flow board / Spec, board luồng Figma |
| 6 | Hand off / Bàn giao | `handoff`, `share` | One zip, email draft / Một file zip, email nháp |

- **After development bar**
  - EN: After development: `verify` compares the developers' build with the approved design; decisions become verified
  - VI: Sau khi phát triển: `verify` so bản developer làm với thiết kế đã duyệt; quyết định chuyển sang đã kiểm chứng
- **Design system loop bar**
  - EN: Design system loop: `review` → `sync` → `contribute` → `document`, feeds back into Set up and Build
  - VI: Vòng design system: `review` → `sync` → `contribute` → `document`, quay lại bước Dựng dự án và Dựng

### 3.2 Any design system (wide card)

*[Visual: `kit.config.json` → `ds/acme/ds.json` (highlighted) → chip.]*

- **Eyebrow**
  - EN: Any design system
  - VI: Mọi design system
- **Heading**
  - EN: Two files point the kit at your design system
  - VI: Hai file nối kit với design system của bạn
- **Text**
  - EN: Nothing is hard-coded. `kit.config.json` holds the language, stack and apps. A `ds.json` profile holds the token prefix, CSS bundle, theming and Figma libraries.
  - VI: Không có gì bị gắn cứng. `kit.config.json` giữ ngôn ngữ, stack và các app. Profile `ds.json` giữ prefix token, gói CSS, theming và thư viện Figma.
- **Chip**
  - EN: 18 skills
  - VI: 18 skill

### 3.3 Contrast check (narrow card)

*[Big number and two small stats from the real test run.]*

- **Eyebrow**
  - EN: Contrast check
  - VI: Kiểm tra tương phản
- **Heading**
  - EN: Every colour pair, light and dark
  - VI: Mọi cặp màu, cả sáng lẫn tối
- **Text**
  - EN: Text needs 4.5:1, icons and borders 3:1. The thresholds are never lowered.
  - VI: Chữ cần đạt 4.5:1, icon và viền cần 3:1. Ngưỡng không bao giờ bị hạ.
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

*[Big number and two small stats.]*

- **Eyebrow**
  - EN: No design system yet
  - VI: Chưa có design system
- **Heading**
  - EN: Start from shadcn
  - VI: Bắt đầu từ shadcn
- **Text**
  - EN: `adopt` takes your brand colour, name, radius and font. The look comes from shadcn, the structure from Material Design 3.
  - VI: `adopt` lấy màu thương hiệu, tên, độ bo góc và font của bạn. Phần giao diện lấy từ shadcn, phần cấu trúc lấy từ Material Design 3.
- **Big number**
  - EN: Components
  - VI: Component
- **Stat 1 label**
  - EN: Touch targets
  - VI: Vùng chạm
- **Stat 2 label**
  - EN: Platforms
  - VI: Nền tảng

### 3.5 Handoff package (wide card)

*[Code block: the real package layout from `skills/handoff/scripts/pkg.py` (AGENTS.md, README.md, requirements/ with checklist-feature.csv, checklist-qc.csv, changelog.md, spec/, prototype/).]*

- **Eyebrow**
  - EN: Handoff package
  - VI: Gói bàn giao
- **Heading**
  - EN: One zip, a reading path for each role
  - VI: Một file zip, mỗi vai trò một lối đọc riêng
- **Text**
  - EN: BA gets the spec and feature list, QC a checklist, developers `AGENTS.md` and the prototype. No screen images and no loose `.js` files, so mail filters let it through.
  - VI: BA nhận spec và danh sách tính năng, QC nhận checklist, developer nhận `AGENTS.md` và prototype. Không có ảnh màn hình, không có file `.js` rời, nên bộ lọc email không chặn.
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
  - EN: Every decision has an owner and a status
  - VI: Mỗi quyết định có người chịu trách nhiệm và trạng thái
- **Text**
  - EN: The kit proposes; a named person approves or rejects. The decision log remembers who decided what and why, across sessions, and follows each decision until the build is verified.
  - VI: Kit đề xuất; một người được nêu tên duyệt hoặc từ chối. Nhật ký quyết định ghi nhớ ai quyết định gì và vì sao, xuyên suốt các phiên làm việc, và theo dõi từng quyết định đến khi bản dựng được kiểm chứng.
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

*[Mini report table: Fail 0 · Needs a human 3 · Skipped 0 (illustration of the validate report).]*

- **Eyebrow**
  - EN: Checked, not just generated
  - VI: Được kiểm chứng, không chỉ được sinh ra
- **Heading**
  - EN: One report says what is broken and what needs a human
  - VI: Một báo cáo nói rõ cái gì hỏng và cái gì cần người xem
- **Text**
  - EN: `validate` runs every screen, state and flow at three widths in light and dark mode. `verify` compares the developers' build with the approved prototype.
  - VI: `validate` chạy mọi màn hình, trạng thái và luồng ở ba kích thước, cả sáng lẫn tối. `verify` so bản developer làm với prototype đã duyệt.
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
  - EN: always with the reason, never as passed
  - VI: luôn kèm lý do, không bao giờ tính là đạt

## 4. How the kit works

*[Seven numbered steps on a vertical line, inside a card. Each step: duotone icon, title, text, skill chips.]*

- **Eyebrow**
  - EN: Workflow
  - VI: Quy trình
- **Heading**
  - EN: How the kit works
  - VI: Kit hoạt động thế nào
- **Intro**
  - EN: One path from a requirement to a verified build. A person decides at every gate; every step is a skill you can also run on its own.
  - VI: Một lộ trình từ yêu cầu đến bản dựng đã kiểm chứng. Người quyết định ở mọi bước duyệt; mỗi bước là một skill bạn cũng có thể chạy riêng.

### Step 1 · Set up the project / Dựng dự án

- EN: Build a base design system if you have none, pick the language, stack and design system, and keep the product's memory: users, principles, rules and decisions.
- VI: Dựng design system nền nếu chưa có, chọn ngôn ngữ, stack và design system, và lưu bộ nhớ sản phẩm: người dùng, nguyên tắc, luật và các quyết định.
- Skills: `adopt` `kickoff` `context`

### Step 2 · Define the work / Xác định phạm vi

- EN: Turn PM and BA requirements into open questions, delivery waves and a traceability matrix. The plan is approved before anything is built.
- VI: Biến yêu cầu của PM và BA thành câu hỏi mở, các đợt bàn giao và ma trận truy vết. Kế hoạch được duyệt trước khi dựng bất cứ thứ gì.
- Skills: `define`

### Step 3 · Explore directions / Khám phá các hướng

- EN: For a real design question, two to four directions built with the DS, side by side. A person chooses one and the reason is recorded.
- VI: Với một câu hỏi thiết kế thật, dựng 2–4 hướng bằng DS và đặt cạnh nhau. Người chọn một hướng và lý do được ghi lại.
- Skills: `explore`

### Step 4 · Build and check the prototype / Dựng và kiểm tra prototype

- EN: Screens use design-system components only; the kit asks before a new component or page. Then it checks errors, accessibility, focus, states and flows in the browser.
- VI: Màn hình chỉ dùng component của design system; kit hỏi trước khi tạo component hoặc trang mới. Sau đó kiểm tra lỗi, accessibility, focus, trạng thái và luồng trên trình duyệt.
- Skills: `prototype` `validate`

### Step 5 · Write the spec / Viết spec

- EN: Screen captures, pins and styles mapped to token names. Flows and screens go on Figma.
- VI: Ảnh chụp màn hình, ghim chú thích và style ánh xạ sang tên token. Luồng và màn hình được đưa lên Figma.
- Skills: `annotate` `wireflow` `mockup`

### Step 6 · Hand off / Bàn giao

- EN: Pack one zip for BA, QC and developers, with the decisions behind the design, and draft the email. The kit never sends it.
- VI: Đóng gói một file zip cho BA, QC và developer, kèm các quyết định đằng sau thiết kế, rồi soạn email. Kit không bao giờ tự gửi.
- Skills: `handoff` `share`

### Step 7 · Verify the build / Kiểm chứng bản dựng

- EN: Once developers have built it, compare their build with the approved prototype. Each difference is a defect or an approved deviation; then the decisions are marked verified.
- VI: Khi developer đã dựng xong, so bản của họ với prototype đã duyệt. Mỗi khác biệt là lỗi hoặc sai lệch đã duyệt; sau đó các quyết định được đánh dấu đã kiểm chứng.
- Skills: `verify`

## 5. A real run

*[Terminal-style console with three tabs. The `//` comment lines are translated; the command output is the real output of a test run and stays in English.]*

- **Heading**
  - EN: A real run
  - VI: Một lần chạy thật
- **Intro**
  - EN: Output from setting up a React project with the kit. Trimmed, numbers unchanged.
  - VI: Output khi dựng một dự án React bằng kit. Đã rút gọn, số liệu giữ nguyên.
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
  - EN: Pick a skill to see what it does. Each one links to its full instructions on GitHub.
  - VI: Chọn một skill để xem nó làm gì. Mỗi skill đều có link tới hướng dẫn đầy đủ trên GitHub.
- **Index label**
  - EN: Skills index
  - VI: Danh sách skill
- **Link**
  - EN: Read SKILL.md on GitHub
  - VI: Đọc SKILL.md trên GitHub

| # | Skill | Group (EN / VI) | Description (EN) | Description (VI) |
|---|---|---|---|---|
| 1 | `brief` | Start / Bắt đầu | Understands a plain-language request and routes it to the right skill with a one-line plan. Use it when you are not sure where to start, or when you have a PRD and some screenshots. | Hiểu yêu cầu viết bằng lời thường và chuyển tới đúng skill kèm kế hoạch một dòng. Dùng khi bạn chưa biết bắt đầu từ đâu, hoặc khi có một PRD và vài ảnh chụp màn hình. |
| 2 | `kickoff` | Start / Bắt đầu | Sets up a project: asks for language, stack, design system and the first app, writes kit.config.json, links and checks the design-system profile, creates the app from the stack template and runs a smoke test. | Dựng dự án: hỏi ngôn ngữ, stack, design system và app đầu tiên, ghi kit.config.json, liên kết và kiểm tra profile design system, tạo app từ template của stack rồi chạy smoke test. |
| 3 | `adopt` | Start / Bắt đầu | Builds a base design system when you have none. The look comes from the shadcn preset, the structure from Material Design 3. You choose the brand colour, name, prefix, radius and font; every colour pair is checked for contrast. | Dựng một design system nền khi bạn chưa có. Giao diện lấy từ preset shadcn, cấu trúc lấy từ Material Design 3. Bạn chọn màu thương hiệu, tên, prefix, độ bo góc và font; mọi cặp màu đều được kiểm tra tương phản. |
| 4 | `context` | Plan and build / Lên kế hoạch và dựng | Keeps the product memory other skills read: overview, personas, UX principles, business rules, constraints, and a decision log where every decision has a status and names who decided. | Giữ bộ nhớ sản phẩm mà các skill khác đọc: tổng quan, persona, nguyên tắc UX, luật nghiệp vụ, ràng buộc, và nhật ký quyết định trong đó mỗi quyết định có trạng thái và tên người quyết định. |
| 5 | `define` | Plan and build / Lên kế hoạch và dựng | Turns PM and BA requirements into units, finds what is vague, missing or contradictory, writes questions, maps units to screens and the component catalogue, and splits the work into delivery waves with acceptance criteria. | Biến yêu cầu của PM và BA thành các unit, tìm chỗ mơ hồ, thiếu hoặc mâu thuẫn, viết câu hỏi, ánh xạ unit sang màn hình và catalogue component, rồi chia việc thành các đợt bàn giao có tiêu chí nghiệm thu. |
| 6 | `explore` | Plan and build / Lên kế hoạch và dựng | Builds two to four meaningfully different directions for one design question with the DS, puts them side by side, and records the direction a person chooses and why. Prototype builds only from a chosen direction. | Dựng 2–4 hướng thật sự khác nhau cho một câu hỏi thiết kế bằng DS, đặt cạnh nhau, và ghi lại hướng mà người chọn cùng lý do. Prototype chỉ dựng từ hướng đã được chọn. |
| 7 | `prototype` | Plan and build / Lên kế hoạch và dựng | Builds screens and flows from a request, a plan wave, reference images or screenshots. Every element is mapped to the design-system catalogue, and it stops to ask before any new component or page. | Dựng màn hình và luồng từ yêu cầu, một đợt trong kế hoạch, ảnh tham khảo hoặc ảnh chụp màn hình. Mỗi phần tử được ánh xạ sang catalogue của design system, và kit dừng lại hỏi trước khi tạo component hoặc trang mới. |
| 8 | `validate` | Quality / Chất lượng | Checks a prototype in the browser at phone, tablet and desktop widths in light and dark mode: errors, overflow, accessibility, keyboard focus, touch targets, states, flows and visual changes. One report separates failures from what a human must judge. | Kiểm tra prototype trên trình duyệt ở cỡ điện thoại, máy tính bảng và máy tính, cả sáng lẫn tối: lỗi, tràn ngang, accessibility, focus bàn phím, vùng chạm, trạng thái, luồng và thay đổi hình ảnh. Một báo cáo tách lỗi khỏi những điểm cần người xem. |
| 9 | `annotate` | Specify / Đặc tả | Writes the design spec for BA, QC and developers: one Markdown file per unit, every screen and state captured, elements pinned with their styles mapped to token names, and the business flow drawn as a wireflow. | Viết spec thiết kế cho BA, QC và developer: mỗi unit một file Markdown, chụp đủ mọi màn hình và trạng thái, ghim phần tử kèm style ánh xạ sang tên token, và vẽ luồng nghiệp vụ dạng wireflow. |
| 10 | `wireflow` | Specify / Đặc tả | Puts the prototype flow on a Figma board: one screenshot per screen, joined by arrows along the business flows, with pins and demo links. It updates the board in place, so shared links keep working. | Đưa luồng prototype lên một board Figma: mỗi màn hình một ảnh chụp, nối bằng mũi tên theo luồng nghiệp vụ, có ghim và link demo. Board được cập nhật tại chỗ nên link đã chia sẻ vẫn dùng được. |
| 11 | `mockup` | Specify / Đặc tả | Rebuilds each screen on Figma as editable layers with auto layout, design-system components and variables, next to the wireflow. An automatic check must pass before it is done. | Dựng lại từng màn hình trên Figma thành layer chỉnh sửa được, có auto layout, component và biến của design system, đặt cạnh wireflow. Phải qua một bước kiểm tra tự động mới xong. |
| 12 | `handoff` | Deliver / Bàn giao | Packages a prototype into one zip for BA, QC and developers: feature list, changelog, QC checklist, a spec per unit and AGENTS.md with reading paths per role. Works for one feature or a whole app version. | Đóng gói prototype thành một file zip cho BA, QC và developer: danh sách tính năng, changelog, checklist QC, spec cho từng unit và AGENTS.md chỉ lối đọc cho từng vai trò. Dùng được cho một tính năng hoặc cả một phiên bản app. |
| 13 | `share` | Deliver / Bàn giao | Drafts the handoff email from a package: subject, Figma link, demo links, key changes for business readers and the zip attached. It only creates a draft; you review and send it. | Soạn email bàn giao từ một gói: tiêu đề, link Figma, link demo, các thay đổi chính viết cho người đọc nghiệp vụ, kèm file zip. Kit chỉ tạo bản nháp; bạn xem lại rồi tự gửi. |
| 14 | `verify` | Quality / Chất lượng | After development, compares the developers' build with the approved prototype: side-by-side screenshots, values outside the DS tokens, missing components, changed texts, flows and accessibility. Differences become defects or approved deviations. | Sau khi phát triển, so bản developer làm với prototype đã duyệt: ảnh ghép cạnh nhau, giá trị ngoài token DS, component bị thiếu, chữ bị đổi, luồng và accessibility. Khác biệt trở thành lỗi hoặc sai lệch đã duyệt. |
| 15 | `review` | Design system / Design system | A read-only audit of how well an app follows the design system: version, tokens, hard-coded values, component use and overrides. Each deviation is classified with options to fix it. | Audit chỉ đọc, đo mức app tuân theo design system: phiên bản, token, giá trị gắn cứng, cách dùng component và các chỗ ghi đè. Mỗi sai lệch được phân loại kèm phương án sửa. |
| 16 | `sync` | Design system / Design system | Brings a new design-system version into your apps: reads the changelog, replaces the embedded CSS or bumps the package, sorts every control, asks before touching local components, then tests and records the change. | Đưa phiên bản design system mới vào các app: đọc changelog, thay CSS nhúng hoặc nâng phiên bản package, phân loại từng control, hỏi trước khi đụng tới component local, rồi test và ghi lại thay đổi. |
| 17 | `contribute` | Design system / Design system | Keeps the local-component registry in step, scores local components and proposes the good ones to the design system through two approval gates. | Giữ danh sách component local khớp với app, chấm điểm component local và đề xuất những cái tốt vào design system qua hai bước duyệt. |
| 18 | `document` | Design system / Design system | Maintains the design-system profile and its docs: changes tokens and components at the source, rebuilds the bundle, bumps the version, writes the changelog and checks contrast. | Duy trì profile design system và tài liệu: sửa token và component tại nguồn, build lại bundle, nâng phiên bản, viết changelog và kiểm tra tương phản. |

## 7. Install

*[Centred card with a soft gold glow. Command box with a Copy button, then a gold GitHub button.]*

- **Version pill**
  - EN: Version 0.6.0 · MIT licence
  - VI: Phiên bản 0.6.0 · Giấy phép MIT
- **Heading**
  - EN: Ready to prototype with your design system?
  - VI: Sẵn sàng dựng prototype với design system của bạn?
- **Text**
  - EN: Run these in Claude Code. The skills are then available as `/kit:<skill>`.
  - VI: Chạy các lệnh sau trong Claude Code. Sau đó các skill có sẵn dưới dạng `/kit:<skill>`.
- **Commands (same in both languages):**

  ```
  /plugin marketplace add MinhNhat0201/nnminh-prototype-kit
  /plugin install kit@nnminh-prototype-kit
  ```

- **Button (→ GitHub)**
  - EN: View on GitHub
  - VI: Xem trên GitHub

## 8. FAQ

*[Accordion in a card. Questions in page order.]*

- **Heading**
  - EN: Frequently asked questions
  - VI: Câu hỏi thường gặp

### What is Prototype Kit?

- VI question: Prototype Kit là gì?
- EN: A Claude Code plugin (`kit@nnminh-prototype-kit`) with 18 skills that take a design from requirement to developer handoff and back: requirement analysis, design directions, prototypes built with your design system, browser checks, specs, Figma flow boards, one handoff package, and a check of the developers' build.
- VI: Một plugin Claude Code (`kit@nnminh-prototype-kit`) gồm 18 skill đưa thiết kế từ yêu cầu đến bàn giao cho developer và ngược lại: phân tích yêu cầu, các hướng thiết kế, prototype dựng bằng design system của bạn, kiểm tra trên trình duyệt, spec, board luồng Figma, một gói bàn giao, và kiểm tra bản developer làm.

### Does the AI make design decisions for us?

- VI question: AI có tự quyết định thiết kế thay chúng tôi không?
- EN: No. The kit proposes and a person decides at every gate: the plan, the design direction, every new component or page, proposals to the DS and any accepted deviation. Decisions are recorded with the name of who made them.
- VI: Không. Kit đề xuất và người quyết định ở mọi bước duyệt: kế hoạch, hướng thiết kế, mọi component hoặc trang mới, đề xuất vào DS và mọi sai lệch được chấp nhận. Mỗi quyết định được ghi kèm tên người quyết định.

### How do I know the prototype really works?

- VI question: Làm sao biết prototype thật sự chạy đúng?
- EN: `validate` opens every screen, state and flow at phone, tablet and desktop widths in light and dark mode and writes one report: what fails, what a person must look at, and what was skipped and why.
- VI: `validate` mở mọi màn hình, trạng thái và luồng ở cỡ điện thoại, máy tính bảng và máy tính, cả sáng lẫn tối, rồi viết một báo cáo: cái gì lỗi, cái gì cần người xem, cái gì bị bỏ qua và vì sao.

### Can it check what developers built?

- VI question: Kit có kiểm tra được bản developer làm không?
- EN: Yes. `verify` compares their build with the approved prototype, screen by screen. A difference is either a defect for developers or an intended change covered by an approved decision.
- VI: Có. `verify` so bản của họ với prototype đã duyệt, từng màn hình một. Mỗi khác biệt hoặc là lỗi để developer sửa, hoặc là thay đổi có chủ đích được một quyết định đã duyệt bao quát.

### Is it free?

- VI question: Có miễn phí không?
- EN: Yes. The kit is released under the MIT licence. The shadcn preset it ships with is derived from shadcn/ui and shadcn-vue, also MIT.
- VI: Có. Kit phát hành theo giấy phép MIT. Preset shadcn đi kèm được dựng từ shadcn/ui và shadcn-vue, cũng theo giấy phép MIT.

### Do I need a design system first?

- VI question: Có cần design system trước không?
- EN: No. Without one, run `adopt`: it builds a base profile from shadcn with your brand colour, name, radius and font. If you have one, write a `ds.json` profile for it and `kickoff` links it.
- VI: Không. Nếu chưa có, chạy `adopt`: skill này dựng một profile nền từ shadcn với màu thương hiệu, tên, độ bo góc và font của bạn. Nếu đã có, hãy viết một profile `ds.json` cho nó và `kickoff` sẽ liên kết vào.

### Which stacks does it support?

- VI question: Kit hỗ trợ những stack nào?
- EN: HTML (the default, one file that opens anywhere), React and Vue. Each app can use its own stack, so they can live side by side in one repository.
- VI: HTML (mặc định, một file mở được ở mọi nơi), React và Vue. Mỗi app có thể dùng stack riêng, nên chúng có thể nằm cạnh nhau trong một repo.

### Does it send emails or publish anything on its own?

- VI question: Kit có tự gửi email hay tự đăng gì không?
- EN: No. `share` only drafts the handoff email for you to review and send. Skills save files; they do not commit, push or publish unless you ask.
- VI: Không. `share` chỉ soạn nháp email bàn giao để bạn xem lại và tự gửi. Các skill chỉ lưu file; chúng không commit, push hay đăng gì trừ khi bạn yêu cầu.

### Do I need Figma?

- VI question: Có cần Figma không?
- EN: Only for `wireflow`, `mockup` and the optional Figma step of `adopt`, which need the Figma connector. Everything else works without it.
- VI: Chỉ cần cho `wireflow`, `mockup` và bước Figma tuỳ chọn của `adopt`, vì các bước này dùng connector Figma. Mọi thứ khác chạy được mà không cần Figma.

### Which languages can the documents be in?

- VI question: Tài liệu sinh ra có thể viết bằng ngôn ngữ nào?
- EN: Replies and generated documents follow `kit.config.json > language`. English and Vietnamese ship with the kit; add a language by copying `locales/en/` and translating the values.
- VI: Câu trả lời và tài liệu sinh ra theo `kit.config.json > language`. Kit có sẵn tiếng Anh và tiếng Việt; muốn thêm ngôn ngữ, sao chép `locales/en/` rồi dịch các giá trị.

### What do I need installed?

- VI question: Cần cài những gì?
- EN: Claude Code, Python 3.9+, Node 18+, Playwright with Chromium for screen capture, and Pillow for image optimisation.
- VI: Claude Code, Python 3.9+, Node 18+, Playwright kèm Chromium để chụp màn hình, và Pillow để tối ưu ảnh.

## 9. Footer

*[Four columns: about, Kit links (same labels as the header), Docs links, Project links. Base line with the version.]*

- **About**
  - EN: Claude Code skills for prototypes and design handoff, with any design system.
  - VI: Skill Claude Code cho prototype và bàn giao thiết kế, dùng với mọi design system.
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
  - EN: Released under the MIT licence. Contributions welcome.
  - VI: Phát hành theo giấy phép MIT. Hoan nghênh đóng góp.
- **Version:** v0.6.0
