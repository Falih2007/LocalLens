import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";
const backend = process.env.LOCALLENS_API_URL;
export default defineConfig(({ command }) => {
  if (command === "serve" && !backend) {
    throw new Error("Set LOCALLENS_API_URL to the URL printed by python app.py --no-window. No laptop-specific port is assumed.");
  }
  return {
    plugins: [react(), tailwindcss(), {
      name: "local-session", apply: "serve",
      async transformIndexHtml(html) {
        try {
          const response = await fetch(backend!);
          const page = await response.text();
          const token = page.match(/name="session-token" content="([^"]+)"/)?.[1];
          if (token) return html.replace("__TOKEN__", token);
        } catch {}
        return html;
      },
    }],
    resolve: { alias: { "@": path.resolve(import.meta.dirname, "./src") } },
    server: { host: "127.0.0.1", proxy: backend ? { "/api": { target: backend, changeOrigin: true } } : undefined },
    build: { outDir: "dist", emptyOutDir: true, license: { fileName: "THIRD-PARTY-LICENSES.md" } },
  };
});
