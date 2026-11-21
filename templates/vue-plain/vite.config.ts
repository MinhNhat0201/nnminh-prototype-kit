import { fileURLToPath, URL } from "node:url"
import { defineConfig } from "vite"
import vue from "@vitejs/plugin-vue"
import { viteSingleFile } from "vite-plugin-singlefile"

// Every build is one self-contained file: dist/index.html with CSS and JS inlined, no separate .js
// (handoff packages never carry loose .js files; hash routing lets it open from a folder or by double-click).
// No Tailwind: styles come from the DS bundle and the app-* skeleton classes in src/index.css.
export default defineConfig({
  base: "./",
  plugins: [vue(), viteSingleFile()],
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)){{EXTRA_ALIASES}} } },
  build: { outDir: "dist", emptyOutDir: true },
})
