/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        progressPink: "#ff2bbf",
        progressPurple: "#8b35ff",
        progressCyan: "#2ee8ff",
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      boxShadow: {
        neonPink: "0 0 28px rgba(255, 43, 191, 0.45)",
        neonPurple: "0 0 34px rgba(139, 53, 255, 0.45)",
      },
    },
  },
  plugins: [],
};
