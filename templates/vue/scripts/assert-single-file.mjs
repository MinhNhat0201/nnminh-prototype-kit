// Checks that the build is handoff-ready: dist/ holds HTML only (no separate .js, .css or .map), and each HTML file
// carries its script inline. Exit 1 with ERROR lines otherwise.
import { readdirSync, readFileSync, statSync } from "node:fs"
import { join } from "node:path"

const dir = "dist"
const files = []
const walk = (d) => readdirSync(d).forEach((f) => (statSync(join(d, f)).isDirectory() ? walk(join(d, f)) : files.push(join(d, f))))
walk(dir)

const errors = []
const html = files.filter((f) => f.endsWith(".html"))
for (const f of files) if (/\.(m?js|css|map)$/.test(f)) errors.push(`separate file ${f}`)
if (!html.length) errors.push("no HTML file in dist/")
for (const f of html) if (/<script[^>]*\ssrc=/i.test(readFileSync(f, "utf8"))) errors.push(`${f} loads an external script`)

if (errors.length) {
  for (const e of errors) console.log("ERROR: " + e)
  process.exit(1)
}
console.log(`Single-file build OK: ${html.join(", ")} (${files.length} file(s) in ${dir}/)`)
