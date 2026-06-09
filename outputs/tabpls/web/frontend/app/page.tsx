"use client";

import { useState } from "react";
import UploadForm from "@/components/UploadForm";
import TabDisplay from "@/components/TabDisplay";

export default function Home() {
  const [tab, setTab] = useState<string | null>(null);
  const [filename, setFilename] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleResult = (tab: string, filename: string) => {
    setTab(tab);
    setFilename(filename);
  };

  return (
    <div className="space-y-8">
      <div className="text-center space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">
          Hear a riff. Get the tab.
        </h1>
        <p style={{ color: "var(--text-muted)" }}>
          Upload a guitar recording and TabPls transcribes it to ASCII tab in seconds.
        </p>
      </div>

      <div
        className="rounded-xl border p-6"
        style={{ borderColor: "var(--border)", background: "var(--surface)" }}
      >
        <UploadForm
          onResult={handleResult}
          onError={setError}
          onLoading={setLoading}
        />
      </div>

      {loading && (
        <div className="text-center py-8">
          <div className="inline-flex items-center gap-3">
            <svg
              className="animate-spin h-5 w-5"
              style={{ color: "var(--accent)" }}
              viewBox="0 0 24 24"
              fill="none"
            >
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
              />
            </svg>
            <span style={{ color: "var(--text-muted)" }}>Transcribing…</span>
          </div>
        </div>
      )}

      {error && (
        <div
          className="rounded-lg border px-4 py-3 text-sm"
          style={{ borderColor: "#f85149", background: "rgba(248,81,73,0.1)", color: "#f85149" }}
        >
          {error}
        </div>
      )}

      {tab && !loading && (
        <TabDisplay tab={tab} filename={filename} />
      )}

      {!tab && !loading && (
        <div className="text-center text-sm space-y-2" style={{ color: "var(--text-muted)" }}>
          <p className="font-medium">Technique notation guide</p>
          <div className="font-mono text-xs space-y-1">
            <p><span style={{ color: "var(--accent-2)" }}>5h7</span> — hammer-on from 5 to 7</p>
            <p><span style={{ color: "var(--accent-2)" }}>7p5</span> — pull-off from 7 to 5</p>
            <p><span style={{ color: "var(--accent-2)" }}>7b9</span> — bend fret 7 up to pitch of fret 9</p>
            <p><span style={{ color: "var(--accent-2)" }}>7~</span>  — vibrato on fret 7</p>
            <p><span style={{ color: "var(--accent-2)" }}>5/9</span> — slide up from 5 to 9</p>
            <p><span style={{ color: "var(--accent-2)" }}>9\5</span> — slide down from 9 to 5</p>
          </div>
        </div>
      )}
    </div>
  );
}
