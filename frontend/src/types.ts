export type FailureType = "TWF" | "HDF" | "PWF" | "OSF";
export type Status = "healthy" | "warning" | "critical";

export const FAILURE_TYPES: FailureType[] = ["HDF", "PWF", "OSF", "TWF"];

export const FAILURE_LABELS: Record<string, string> = {
  NONE: "No failure",
  TWF: "Tool wear",
  HDF: "Heat dissipation",
  PWF: "Power",
  OSF: "Overstrain",
};

export interface Reading {
  machine_id: string;
  air_temp_k: number;
  process_temp_k: number;
  rpm: number;
  torque_nm: number;
  tool_wear_min: number;
  quality: "L" | "M" | "H";
  injected_fault: FailureType | null;
}

export interface Prediction {
  risk: number;
  failure_type: FailureType;
  probabilities: Record<string, number>;
}

export interface ReadingRecord {
  ts: string;
  reading: Reading;
  prediction: Prediction;
  status: Status;
}

export interface Machine {
  machine_id: string;
  latest: ReadingRecord | null;
  pending_fault: FailureType | null;
}

export interface AlertSummary {
  alert_id: string;
  ts: string;
  machine_id: string;
  failure_type: FailureType;
  risk: number;
  grounded: boolean;
}

export interface Citation {
  source: string;
  snippet: string;
}

export interface AlertDetail extends AlertSummary {
  reading: Reading;
  prediction: Prediction;
  explanation: string;
  citations: Citation[];
  model_id: string;
  latency_ms: number;
}
