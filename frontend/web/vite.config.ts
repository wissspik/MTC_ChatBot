import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const allowedHosts = env.VITE_ALLOWED_HOSTS
    ? env.VITE_ALLOWED_HOSTS.split(",").map((host) => host.trim()).filter(Boolean)
    : [".ngrok-free.app", ".ngrok-free.dev"];

  return {
    plugins: [react()],
    server: {
      host: "0.0.0.0",
      allowedHosts,
    },
  };
});
