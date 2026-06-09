import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "TabPls — Guitar Tab Transcription",
  description: "Upload a guitar recording and get ASCII tab in seconds.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen" style={{ background: "var(--bg)", color: "var(--text)" }}>
        <header
          className="border-b px-6 py-4 flex items-center gap-3"
          style={{ borderColor: "var(--border)", background: "var(--surface)" }}
        >
          <span className="text-2xl">🎸</span>
          <span className="text-xl font-semibold tracking-tight">TabPls</span>
          <span className="text-sm ml-2" style={{ color: "var(--text-muted)" }}>
            audio → guitar tab
          </span>
        </header>
        <main className="max-w-4xl mx-auto px-4 py-8">{children}</main>
        <footer
          className="text-center text-xs py-6 border-t"
          style={{ color: "var(--text-muted)", borderColor: "var(--border)" }}
        >
          TabPls v0.2 · Powered by BasicPitch + Demucs
        </footer>
      </body>
    </html>
  );
}
