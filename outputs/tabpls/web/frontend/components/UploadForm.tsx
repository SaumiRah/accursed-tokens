"use client";

import { useRef, useState } from "react";

const TUNINGS = [
  { value: "standard", label: "Standard (EADGBe)" },
  { value: "drop_d", label: "Drop D (DADGBe)" },
  { value: "open_g", label: "Open G (DGDGBd)" },
  { value: "open_e", label: "Open E (EBE G#Be)" },
  { value: "half_step", label: "Half-step down (Eb Ab Db Gb Bb eb)" },
  { value: "full_step", label: "Full-step down (D G C F A d)" },
];

interface UploadFormProps {
  onResult: (tab: string, filename: string) => void;
  onError: (msg: string) => void;
  onLoading: (loading: boolean) => void;
}

export default function UploadForm({ onResult, onError, onLoading }: UploadFormProps) {
  const [dragging, setDragging] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [tuning, setTuning] = useState("standard");
  const [bpm, setBpm] = useState(120);
  const [separate, setSeparate] = useState(false);
  const [techniques, setTechniques] = useState(true);
  const fileRef = useRef<HTMLInputElement>(null);
  const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

  const handleFile = (f: File) => {
    setFile(f);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files[0];
    if (f) handleFile(f);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;

    onLoading(true);
    onError("");

    const form = new FormData();
    form.append("audio", file);
    form.append("tuning", tuning);
    form.append("bpm", String(bpm));
    form.append("separate", String(separate));
    form.append("detect_techniques", String(techniques));

    try {
      const res = await fetch(`${apiBase}/transcribe`, {
        method: "POST",
        body: form,
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        onError(err.detail ?? "Transcription failed.");
        return;
      }
      const tab = await res.text();
      onResult(tab, file.name);
    } catch (err: unknown) {
      onError(err instanceof Error ? err.message : "Network error — is the backend running?");
    } finally {
      onLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {/* Drop zone */}
      <div
        onClick={() => fileRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        className="rounded-lg border-2 border-dashed p-10 text-center cursor-pointer transition-colors"
        style={{
          borderColor: dragging ? "var(--accent)" : "var(--border)",
          background: dragging ? "rgba(247,129,102,0.05)" : "var(--surface)",
        }}
      >
        <input
          ref={fileRef}
          type="file"
          accept=".mp3,.wav,.flac,.ogg,.m4a,.aac"
          className="hidden"
          onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
        />
        <p className="text-2xl mb-2">🎵</p>
        {file ? (
          <p className="font-medium">{file.name}</p>
        ) : (
          <>
            <p className="font-medium">Drop a guitar recording here</p>
            <p className="text-sm mt-1" style={{ color: "var(--text-muted)" }}>
              .mp3, .wav, .flac, .ogg — up to 50 MB
            </p>
          </>
        )}
      </div>

      {/* Settings */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium mb-1">Tuning</label>
          <select
            value={tuning}
            onChange={(e) => setTuning(e.target.value)}
            className="w-full rounded px-3 py-2 text-sm border"
            style={{
              background: "var(--surface)",
              borderColor: "var(--border)",
              color: "var(--text)",
            }}
          >
            {TUNINGS.map((t) => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">Tempo (BPM)</label>
          <input
            type="number"
            min={20} max={300}
            value={bpm}
            onChange={(e) => setBpm(Number(e.target.value))}
            className="w-full rounded px-3 py-2 text-sm border"
            style={{
              background: "var(--surface)",
              borderColor: "var(--border)",
              color: "var(--text)",
            }}
          />
        </div>
      </div>

      <div className="flex gap-6">
        <label className="flex items-center gap-2 cursor-pointer text-sm">
          <input
            type="checkbox"
            checked={separate}
            onChange={(e) => setSeparate(e.target.checked)}
            className="rounded"
          />
          <span>Source separation</span>
          <span className="text-xs" style={{ color: "var(--text-muted)" }}>(slower, better for full mixes)</span>
        </label>
        <label className="flex items-center gap-2 cursor-pointer text-sm">
          <input
            type="checkbox"
            checked={techniques}
            onChange={(e) => setTechniques(e.target.checked)}
            className="rounded"
          />
          <span>Detect techniques</span>
          <span className="text-xs" style={{ color: "var(--text-muted)" }}>(h/p/b/~)</span>
        </label>
      </div>

      <button
        type="submit"
        disabled={!file}
        className="w-full py-3 rounded-lg font-semibold text-sm transition-opacity disabled:opacity-40"
        style={{ background: "var(--accent)", color: "#0d1117" }}
      >
        Transcribe
      </button>
    </form>
  );
}
