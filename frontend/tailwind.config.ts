import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: {
          0: "var(--bg-0)",
          1: "var(--bg-1)",
          2: "var(--bg-2)",
        },
        text: {
          1: "var(--text-1)",
          2: "var(--text-2)",
          3: "var(--text-3)",
        },
        accent: {
          DEFAULT: "var(--accent)",
          2: "var(--accent-2)",
        },
        viral: "var(--viral)",
        calm: "var(--calm)",
        danger: "var(--danger)",
        success: "var(--success)",
        /* Retained aliases so existing utilities keep resolving cleanly */
        navy: {
          950: "#070B16",
          900: "#0C1324",
          800: "#121C33",
          700: "#1E2C4D",
          600: "#2C3F6B",
        },
      },
      borderColor: {
        subtle: "var(--border)",
      },
      fontFamily: {
        display: ['"Space Grotesk Variable"', '"Space Grotesk Fallback"', "system-ui", "sans-serif"],
        sans: ['"Inter Variable"', '"Inter Fallback"', "system-ui", "-apple-system", "sans-serif"],
        mono: ['"JetBrains Mono Variable"', '"JetBrains Mono Fallback"', "ui-monospace", "monospace"],
      },
      borderRadius: {
        panel: "16px",
      },
      boxShadow: {
        panel: "inset 0 1px 0 rgba(255,255,255,0.04), 0 12px 32px -12px rgba(2, 6, 23, 0.75)",
        glass: "inset 0 1px 0 rgba(255,255,255,0.06), 0 16px 40px -12px rgba(2, 6, 23, 0.85)",
      },
    },
  },
  plugins: [],
} satisfies Config;
