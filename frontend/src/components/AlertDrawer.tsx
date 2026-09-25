import { useEffect } from "react";
import { api } from "../api";
import { powerW, tempDiffK } from "../physics";
import { FAILURE_LABELS } from "../types";
import { usePolling } from "../usePolling";
import { Markdown } from "./Markdown";

export function AlertDrawer({ alertId, onClose }: { alertId: string; onClose: () => void }) {
  const { data: alert, error } = usePolling(() => api.alert(alertId), 60_000, [alertId]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <aside className="drawer" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
        <button className="close" onClick={onClose} aria-label="Close">×</button>
        {error && <p className="error">{error}</p>}
        {!alert ? (
          <p className="empty">Loading diagnosis…</p>
        ) : (
          <>
            <p className="eyebrow">Alert · {new Date(alert.ts).toLocaleString()}</p>
            <h2>
              {alert.machine_id.toUpperCase()} — {FAILURE_LABELS[alert.failure_type]} failure
            </h2>
            <div className="drawer-stats">
              <div><span>Risk</span><strong className="danger">{Math.round(alert.risk * 100)}%</strong></div>
              <div><span>ΔT</span><strong>{tempDiffK(alert.reading).toFixed(1)} K</strong></div>
              <div><span>Speed</span><strong>{alert.reading.rpm.toFixed(0)} rpm</strong></div>
              <div><span>Torque</span><strong>{alert.reading.torque_nm.toFixed(1)} Nm</strong></div>
              <div><span>Power</span><strong>{(powerW(alert.reading) / 1000).toFixed(2)} kW</strong></div>
              <div><span>Wear</span><strong>{alert.reading.tool_wear_min.toFixed(0)} min</strong></div>
            </div>

            <div className="probabilities">
              {Object.entries(alert.prediction.probabilities)
                .filter(([k]) => k !== "NONE")
                .sort((a, b) => b[1] - a[1])
                .map(([k, p]) => (
                  <div key={k} className="prob-row">
                    <span>{k}</span>
                    <div className="prob-bar"><div style={{ width: `${p * 100}%` }} /></div>
                    <span className="mono">{(p * 100).toFixed(1)}%</span>
                  </div>
                ))}
            </div>

            <section className="diagnosis">
              <div className="diagnosis-head">
                <h3>AI diagnosis</h3>
                <span className={`pill ${alert.grounded ? "grounded" : "ungrounded"}`}>
                  {alert.grounded ? "Grounded in manuals" : "Not grounded"}
                </span>
              </div>
              <Markdown text={alert.explanation} />
              <p className="muted small">
                {alert.model_id} · Bedrock Knowledge Base (S3 Vectors) · {alert.latency_ms} ms
              </p>
            </section>

            {alert.citations.length > 0 && (
              <section className="citations">
                <h3>Sources</h3>
                {alert.citations.map((c, i) => (
                  <blockquote key={i}>
                    <cite>[{i + 1}] {c.source}</cite>
                    <p>{c.snippet}</p>
                  </blockquote>
                ))}
              </section>
            )}
          </>
        )}
      </aside>
    </div>
  );
}
