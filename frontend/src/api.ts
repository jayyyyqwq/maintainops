import type { AlertDetail, AlertSummary, FailureType, Machine, ReadingRecord } from "./types";

interface Envelope<T> {
  success: boolean;
  data: T | null;
  error: string | null;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (response.status === 429) throw new Error("Slow down: demo actions are rate limited");
  let body: Envelope<T>;
  try {
    body = (await response.json()) as Envelope<T>;
  } catch {
    throw new Error(`API returned ${response.status}`);
  }
  if (!response.ok || !body.success || body.data === null) {
    throw new Error(body.error ?? `API returned ${response.status}`);
  }
  return body.data;
}

export const api = {
  machines: () => request<{ machines: Machine[]; simulator_enabled: boolean }>("/machines"),
  readings: (machineId: string, limit = 60) =>
    request<{ readings: ReadingRecord[] }>(`/machines/${machineId}/readings?limit=${limit}`),
  alerts: () => request<{ alerts: AlertSummary[] }>("/alerts?limit=25"),
  alert: (alertId: string) => request<AlertDetail>(`/alerts/${encodeURIComponent(alertId)}`),
  injectFault: (machineId: string, fault: FailureType) =>
    request<{ fault: string }>(`/machines/${machineId}/fault`, {
      method: "POST",
      body: JSON.stringify({ fault }),
    }),
  setSimulator: (enabled: boolean) =>
    request<{ simulator_enabled: boolean }>("/simulator", {
      method: "POST",
      body: JSON.stringify({ enabled }),
    }),
};
