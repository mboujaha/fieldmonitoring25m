import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        earth: {
          50: "#f4f6ef",
          100: "#e7ebdd",
          600: "#416a3f",
          700: "#2f5032",
          900: "#18261a",
        },
      },
      boxShadow: {
        panel: "0 10px 30px rgba(0, 0, 0, 0.15)",
      },
    },
  },
  plugins: [],
};

export default config;
