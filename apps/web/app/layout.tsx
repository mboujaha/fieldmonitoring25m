import "maplibre-gl/dist/maplibre-gl.css";
import "@mapbox/mapbox-gl-draw/dist/mapbox-gl-draw.css";
import "./globals.css";
import { ReactNode } from "react";
import { Space_Grotesk } from "next/font/google";

import { Providers } from "./providers";

const spaceGrotesk = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-space-grotesk",
  display: "swap",
});

export const metadata = {
  title: "Field Monitor Hybrid",
  description: "Polygon-first agriculture monitoring with native and SR workflows",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body className={spaceGrotesk.variable}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
