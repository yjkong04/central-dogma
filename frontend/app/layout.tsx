import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PaperLens — cited answers over papers",
  description: "Multimodal RAG viewer: grounded, cited answers over scientific papers.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
