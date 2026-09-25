import { useCallback, useState } from "react";
import { api } from "./api";
import { AlertDrawer } from "./components/AlertDrawer";
import { AlertFeed } from "./components/AlertFeed";
import { MachineCard } from "./components/MachineCard";
import { SensorPanel } from "./components/SensorPanel";
import type { FailureType } from "./types";
import { usePolling } from "./usePolling";

export default function App() {
  const fleet = usePolling(api.machines, 5000);
  const alerts = usePolling(api.alerts, 5000);
  const [selected, setSelected] = useState("m1");
  const [openAlert, setOpenAlert] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [toggling, setToggling] = useState(false);

  const notify = (message: string) => {
    setToast(message);
    window.setTimeout(() => setToast(null), 4000);
  };

  const inject = useCallback(async (machineId: string, fault: FailureType) => {
    try {
      await api.injectFault(machineId, fault);
      setSelected(machineId);
      notify(`${fault} injected into ${machineId.toUpperCase()} — watch the risk climb`);
      window.setTimeout(() => void fleet.refresh(), 2500);
    } catch (err) {
      notify(err instanceof Error ? err.message : "Injection failed");
    }
  }, [fleet]);

  const toggleSimulator = async () => {
    if (!fleet.data) return;
    setToggling(true);
    try {
      await api.setSimulator(!fleet.data.simulator_enabled);
      await fleet.refresh();
    } catch (err) {
      notify(err instanceof Error ? err.message : "Toggle failed");
    } finally {
      setToggling(false);
    }
  };

  const machines = fleet.data?.machines ?? [];
  const counts = { healthy: 0, warning: 0, critical: 0 };
  for (const m of machines) if (m.latest) counts[m.latest.status] += 1;
  const running = fleet.data?.simulator_enabled ?? false;

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <svg viewBox="0 0 32 32" width="28" height="28" aria-hidden>
            <rect width="32" height="32" rx="6" fill="#f5a524" />
            <path d="M8 22 L13 12 L17 18 L20 14 L24 22" stroke="#0b0f14" strokeWidth="3" fill="none"
                  strokeLinejoin="round" />
          </svg>
          <div>
            <h1>MaintainOps</h1>
            <p>Predictive maintenance · SageMaker XGBoost + Bedrock RAG</p>
          </div>
        </div>
        <div className="summary">
          <span className="count healthy">{counts.healthy} healthy</span>
          <span className="count warning">{counts.warning} warning</span>
          <span className="count critical">{counts.critical} critical</span>
        </div>
        <button className={`sim-toggle ${running ? "on" : ""}`} onClick={toggleSimulator}
                disabled={toggling || !fleet.data}>
          <span className="dot" /> Simulator {running ? "running" : "stopped"}
        </button>
      </header>

      {fleet.error && <div className="banner error">API unreachable: {fleet.error}</div>}

      <main className="layout">
        <div className="left">
          <section className="machine-grid">
            {machines.map((m) => (
              <MachineCard
                key={m.machine_id}
                machine={m}
                selected={m.machine_id === selected}
                onSelect={() => setSelected(m.machine_id)}
                onInject={(fault) => inject(m.machine_id, fault)}
              />
            ))}
          </section>
          <SensorPanel machineId={selected} />
        </div>
        <AlertFeed alerts={alerts.data?.alerts ?? []} activeId={openAlert} onOpen={setOpenAlert} />
      </main>

      <footer className="credits">
        Data: AI4I 2020 Predictive Maintenance Dataset (UCI, CC BY 4.0) · Serverless on AWS
      </footer>

      {openAlert && <AlertDrawer alertId={openAlert} onClose={() => setOpenAlert(null)} />}
      {toast && <div className="toast">{toast}</div>}
    </div>
  );
}
