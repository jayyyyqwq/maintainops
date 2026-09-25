import { useState } from "react";
import { powerW, tempDiffK, violations } from "../physics";
import { FAILURE_LABELS, FAILURE_TYPES, type FailureType, type Machine } from "../types";

interface Props {
  machine: Machine;
  selected: boolean;
  onSelect: () => void;
  onInject: (fault: FailureType) => Promise<void>;
}

export function MachineCard({ machine, selected, onSelect, onInject }: Props) {
  const [fault, setFault] = useState<FailureType>("HDF");
  const [busy, setBusy] = useState(false);
  const latest = machine.latest;
  const status = latest?.status ?? "no data";
  const risk = latest?.prediction.risk ?? 0;
  const r = latest?.reading;

  const inject = async (event: React.MouseEvent) => {
    event.stopPropagation();
    setBusy(true);
    try {
      await onInject(fault);
    } finally {
      setBusy(false);
    }
  };

  return (
    <article
      className={`machine-card status-${status.replace(" ", "-")} ${selected ? "selected" : ""}`}
      onClick={onSelect}
      tabIndex={0}
      onKeyDown={(e) => e.key === "Enter" && onSelect()}
      aria-label={`Machine ${machine.machine_id}, ${status}`}
    >
      <header>
        <span className="machine-id">{machine.machine_id.toUpperCase()}</span>
        {r && <span className="quality">Q-{r.quality}</span>}
        <span className={`badge badge-${status.replace(" ", "-")}`}>{status}</span>
      </header>

      <div className="risk">
        <div className="risk-label">
          <span>Failure risk</span>
          <strong>{latest ? `${(risk * 100).toFixed(0)}%` : "—"}</strong>
        </div>
        <div className="risk-bar">
          <div className="risk-fill" style={{ width: latest ? `${Math.max(risk * 100, 2)}%` : "0%" }} />
          <div className="risk-threshold" title="Alert threshold 50%" />
        </div>
        <div className="risk-type">
          {risk >= 0.25 && latest ? `Likely: ${FAILURE_LABELS[latest.prediction.failure_type]}` : " "}
        </div>
      </div>

      {r ? (
        <dl className="metrics">
          <div><dt>ΔT</dt><dd>{tempDiffK(r).toFixed(1)} K</dd></div>
          <div><dt>Speed</dt><dd>{r.rpm.toFixed(0)} rpm</dd></div>
          <div><dt>Torque</dt><dd>{r.torque_nm.toFixed(1)} Nm</dd></div>
          <div><dt>Power</dt><dd>{(powerW(r) / 1000).toFixed(2)} kW</dd></div>
          <div><dt>Tool wear</dt><dd>{r.tool_wear_min.toFixed(0)} min</dd></div>
          <div><dt>Air</dt><dd>{r.air_temp_k.toFixed(1)} K</dd></div>
        </dl>
      ) : (
        <p className="empty">No readings yet — start the simulator.</p>
      )}

      {r && violations(r).length > 0 && (
        <ul className="violations">{violations(r).map((v) => <li key={v}>{v}</li>)}</ul>
      )}

      <footer onClick={(e) => e.stopPropagation()}>
        <select
          value={fault}
          onChange={(e) => setFault(e.target.value as FailureType)}
          aria-label="Fault type to inject"
        >
          {FAILURE_TYPES.map((f) => (
            <option key={f} value={f}>{f} · {FAILURE_LABELS[f]}</option>
          ))}
        </select>
        <button className="inject" onClick={inject} disabled={busy || Boolean(machine.pending_fault)}>
          {machine.pending_fault ? `${machine.pending_fault} active` : busy ? "Injecting…" : "Inject fault"}
        </button>
      </footer>
    </article>
  );
}
