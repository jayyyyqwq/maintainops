import { FAILURE_LABELS, type AlertSummary } from "../types";

const ago = (ts: string) => {
  const s = Math.max(0, (Date.now() - new Date(ts).getTime()) / 1000);
  if (s < 60) return `${Math.round(s)}s ago`;
  if (s < 3600) return `${Math.round(s / 60)}m ago`;
  if (s < 86400) return `${Math.round(s / 3600)}h ago`;
  return `${Math.round(s / 86400)}d ago`;
};

interface Props {
  alerts: AlertSummary[];
  activeId: string | null;
  onOpen: (alertId: string) => void;
}

export function AlertFeed({ alerts, activeId, onOpen }: Props) {
  return (
    <section className="panel alert-feed">
      <div className="panel-title">
        <h2>Alerts</h2>
        <span className="muted">AI diagnosis via Bedrock</span>
      </div>
      {alerts.length === 0 && <p className="empty">No alerts yet. Inject a fault to trigger one.</p>}
      <ul>
        {alerts.map((a) => (
          <li key={a.alert_id}>
            <button className={activeId === a.alert_id ? "active" : ""} onClick={() => onOpen(a.alert_id)}>
              <span className="alert-risk">{Math.round(a.risk * 100)}%</span>
              <span className="alert-body">
                <strong>{a.machine_id.toUpperCase()} · {FAILURE_LABELS[a.failure_type] ?? a.failure_type}</strong>
                <span className="muted">
                  {ago(a.ts)} · {a.grounded ? "cited from manuals" : "not grounded"}
                </span>
              </span>
              <span className={`pill ${a.failure_type}`}>{a.failure_type}</span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
