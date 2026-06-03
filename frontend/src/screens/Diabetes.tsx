import { useEffect, useRef, useState } from "react";
import { get, getToken, post } from "../api";

type Record_ = {
  window_start: string;
  window_end: string;
  glucose: { average: number | null; time_in_range_pct: number | null; count: number };
  insulin_events: number;
  pump_uploaded: boolean;
};

export default function Diabetes() {
  const [rec, setRec] = useState<Record_ | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const load = () => get<Record_>("/diabetes/record").then(setRec);
  useEffect(() => {
    load();
  }, []);

  const sync = async () => {
    setMsg(null);
    try {
      await post("/diabetes/sync");
      load();
    } catch {
      setMsg("Tidepool API not connected — use the JSON upload below instead.");
    }
  };

  const detectPump = async () => {
    setMsg(null);
    type SerialInfo = { usbVendorId?: number; usbProductId?: number };
    type SerialApi = { requestPort: () => Promise<{ getInfo: () => SerialInfo }> };
    const serial = (navigator as unknown as { serial?: SerialApi }).serial;
    if (!serial) {
      setMsg("This browser has no WebSerial — use Chrome or Edge on desktop.");
      return;
    }
    try {
      const port = await serial.requestPort();
      const info = port.getInfo();
      const hex = (n?: number) => (n != null ? n.toString(16) : "?");
      setMsg(
        `Detected a serial device (vendor 0x${hex(info.usbVendorId)}, product 0x${hex(
          info.usbProductId,
        )}). Decoding the Tandem protocol isn't built yet — for now, export JSON and upload above.`,
      );
    } catch {
      setMsg("No device selected, or access was denied.");
    }
  };

  const upload = async (file: File) => {
    setMsg("Uploading…");
    const fd = new FormData();
    fd.append("file", file);
    const res = await fetch("/api/v1/diabetes/upload", {
      method: "POST",
      headers: { Authorization: `Bearer ${getToken()}` },
      body: fd,
    });
    if (res.ok) {
      const r = (await res.json()) as { glucose_added: number; insulin_added: number };
      setMsg(`Added ${r.glucose_added} glucose readings, ${r.insulin_added} insulin events.`);
      load();
    } else {
      setMsg("Upload failed — expected a Tidepool data-model JSON array.");
    }
    if (fileRef.current) fileRef.current.value = "";
  };

  return (
    <div className="space-y-5">
      <h1 className="text-2xl font-bold">Diabetes record</h1>

      <section className="space-y-2 rounded bg-slate-800 p-3">
        <h2 className="font-semibold">Upload Tidepool data export</h2>
        <p className="text-xs text-slate-500">
          Open-source path: export the Tidepool data-model JSON (e.g. via the
          <code className="mx-1">@tidepool/data-tools</code> CLI) and upload it here — no
          Tidepool account needed. Glucose (cbg/smbg) and insulin (bolus/basal) are ingested.
        </p>
        <input
          ref={fileRef}
          type="file"
          accept="application/json,.json"
          onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])}
          className="text-sm"
        />
      </section>

      <div className="flex flex-wrap gap-2">
        <button onClick={sync} className="rounded bg-slate-800 px-3 py-1 text-sm">
          Or pull from Tidepool API
        </button>
        <button onClick={detectPump} className="rounded bg-slate-800 px-3 py-1 text-sm">
          Detect pump (experimental)
        </button>
      </div>

      {msg && <p className="text-sm text-amber-300">{msg}</p>}

      {rec && (
        <div className="space-y-1 text-sm">
          <p className="text-slate-400">
            {rec.window_start} → {rec.window_end}
          </p>
          <p>Glucose avg: {rec.glucose.average ?? "—"} mmol/L</p>
          <p>Time in range: {rec.glucose.time_in_range_pct ?? "—"}%</p>
          <p>Insulin events: {rec.insulin_events}</p>
          {!rec.pump_uploaded && (
            <p className="text-amber-300">No pump data in this window yet.</p>
          )}
        </div>
      )}
    </div>
  );
}
