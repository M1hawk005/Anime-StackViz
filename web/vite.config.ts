import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Relative base so the static build can be hosted from any CDN path.
export default defineConfig({
  base: "./",
  plugins: [react()],
});
