"use client";

interface TabDisplayProps {
  tab: string;
  filename?: string;
}

export default function TabDisplay({ tab, filename }: TabDisplayProps) {
  const handleDownload = () => {
    const blob = new Blob([tab], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename
      ? filename.replace(/\.[^.]+$/, ".txt")
      : "tab.txt";
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleCopy = async () => {
    await navigator.clipboard.writeText(tab);
  };

  return (
    <div
      className="rounded-lg border overflow-hidden"
      style={{ borderColor: "var(--border)", background: "var(--surface)" }}
    >
      <div
        className="flex items-center justify-between px-4 py-2 border-b"
        style={{ borderColor: "var(--border)" }}
      >
        <span className="text-sm font-medium" style={{ color: "var(--text-muted)" }}>
          Guitar Tab
        </span>
        <div className="flex gap-2">
          <button
            onClick={handleCopy}
            className="text-xs px-3 py-1 rounded border transition-colors hover:opacity-80"
            style={{ borderColor: "var(--border)", color: "var(--text-muted)" }}
          >
            Copy
          </button>
          <button
            onClick={handleDownload}
            className="text-xs px-3 py-1 rounded transition-colors"
            style={{ background: "var(--accent)", color: "#0d1117" }}
          >
            Download
          </button>
        </div>
      </div>
      <pre
        className="p-4 text-sm overflow-x-auto leading-relaxed"
        style={{ fontFamily: "var(--font-mono, monospace)", color: "var(--text)" }}
      >
        {tab}
      </pre>
    </div>
  );
}
