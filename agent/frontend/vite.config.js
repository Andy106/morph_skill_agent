import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
    proxy: {
      // An analysis can take a minute or more while the model works, so don't time out.
      "/api": { target: "http://127.0.0.1:8001", timeout: 0, proxyTimeout: 0 },
    },
  },
});
