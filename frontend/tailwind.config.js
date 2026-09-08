/** @type {import('tailwindcss').Config} */
const v = (name) => `rgb(var(${name}) / <alpha-value>)`;

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      fontFamily: {
        sans: [
          "Roboto",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
        mono: ["JetBrains Mono", "SFMono-Regular", "Menlo", "Consolas", "monospace"],
      },
      colors: {
        primary: {
          DEFAULT: v("--c-primary"),
          fg: v("--c-primary-fg"),
          container: v("--c-primary-container"),
          "on-container": v("--c-primary-on-container"),
        },
        surface: {
          DEFAULT: v("--c-surface"),
          variant: v("--c-surface-variant"),
          border: v("--c-border"),
        },
        fg: {
          DEFAULT: v("--c-fg"),
          muted: v("--c-fg-muted"),
          faint: v("--c-fg-faint"),
        },
        ok: v("--c-ok"),
        danger: v("--c-danger"),
        warn: v("--c-warn"),
        info: v("--c-info"),
      },
      boxShadow: {
        e1: "0 1px 2px 0 rgb(0 0 0 / 0.06), 0 1px 3px 1px rgb(0 0 0 / 0.05)",
        e2: "0 1px 2px 0 rgb(0 0 0 / 0.08), 0 2px 6px 2px rgb(0 0 0 / 0.06)",
        e3: "0 4px 8px 3px rgb(0 0 0 / 0.10), 0 1px 3px 0 rgb(0 0 0 / 0.12)",
        e4: "0 8px 12px 6px rgb(0 0 0 / 0.12), 0 4px 4px 0 rgb(0 0 0 / 0.16)",
      },
      borderRadius: { md: "0.5rem", lg: "0.75rem", xl: "1rem" },
      keyframes: {
        "fade-in": { from: { opacity: "0" }, to: { opacity: "1" } },
        "slide-up": {
          from: { opacity: "0", transform: "translateY(8px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "indeterminate": {
          "0%": { transform: "translateX(-100%) scaleX(0.4)" },
          "50%": { transform: "translateX(20%) scaleX(0.6)" },
          "100%": { transform: "translateX(120%) scaleX(0.4)" },
        },
        "slide-in-right": {
          from: { opacity: "0", transform: "translateX(16px)" },
          to: { opacity: "1", transform: "translateX(0)" },
        },
      },
      animation: {
        "fade-in": "fade-in 120ms ease-out both",
        "slide-up": "slide-up 160ms cubic-bezier(0.2,0,0,1) both",
        "slide-in-right": "slide-in-right 180ms cubic-bezier(0.2,0,0,1) both",
        "indeterminate": "indeterminate 1.4s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
