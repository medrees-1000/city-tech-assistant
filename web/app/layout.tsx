import type { Metadata, Viewport } from "next";
import { ClerkProvider } from "@clerk/nextjs";
import type { ReactNode } from "react";

import "./globals.css";

export const metadata: Metadata = {
  title: "City Tech Assistant",
  description:
    "Unofficial student project: answers questions about City Tech registration, deadlines, aid and four departments, with sources.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  colorScheme: "light dark",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <ClerkProvider>{children}</ClerkProvider>
      </body>
    </html>
  );
}
