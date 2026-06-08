import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        space: "#0A0E1A",
        armor: "#F0F4F8",
        gundam: "#1E40AF",
        zeon: "#DC2626",
        vfin: "#EAB308",
        gunmetal: "#374151",
        beam: "#3B82F6",
      },
      fontFamily: {
        display: ["Oxanium", "Rajdhani", "Segoe UI", "sans-serif"],
        body: ["Rajdhani", "Segoe UI", "sans-serif"],
        mono: ["JetBrains Mono", "Consolas", "monospace"],
      },
      boxShadow: {
        beam: "0 0 32px rgba(59, 130, 246, 0.35)",
        warning: "0 0 28px rgba(234, 179, 8, 0.28)",
      },
    },
  },
  plugins: [],
} satisfies Config;
