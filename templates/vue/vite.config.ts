import { fileURLToPath, URL } from "node:url"
import { defineConfig } from "vite"
import vue from "@vitejs/plugin-vue"
import tailwindcss from "@tailwindcss/vite"
import { viteSingleFile } from "vite-plugin-singlefile"

// Every build is one self-contained file: dist/index.html with CSS and JS inlined, no separate .js
// (handoff packages never carry loose .js files; hash routing lets it open from a folder or by double-click).
export default defineConfig({
  base: "./",
  plugins: [vue(), tailwindcss(), viteSingleFile()],
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  build: { outDir: "dist", emptyOutDir: true },
})
