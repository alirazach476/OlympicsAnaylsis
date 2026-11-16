/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx,js,jsx}"],
  darkMode: ["class", '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        bg: "rgb(var(--bg) / <alpha-value>)", surface: "rgb(var(--surface) / <alpha-value>)", surface2: "rgb(var(--surface2) / <alpha-value>)",
        line: "rgb(var(--line) / <alpha-value>)", ink: "rgb(var(--ink) / <alpha-value>)", muted: "rgb(var(--muted) / <alpha-value>)",
        accent: "rgb(var(--accent) / <alpha-value>)", blue: "#0085C7", yellow: "#F4C300", green: "#009F3D", red: "#DF0024",
        gold: "#D4AF37", silver: "#C0C7D1", bronze: "#CD7F32",
      },
      fontFamily: { display: ['"Barlow Condensed"', "Impact", "sans-serif"], sans: ["Inter", "system-ui", "sans-serif"], mono: ['"JetBrains Mono"', "ui-monospace", "monospace"] },
      boxShadow: { card: "0 1px 0 rgb(255 255 255 / 0.04) inset, 0 12px 30px -18px rgb(0 0 0 / 0.6)" },
    },
  },
  plugins: [],
};
