import type { Reading } from "./types";

export const powerW = (r: Reading) => (r.torque_nm * r.rpm * 2 * Math.PI) / 60;
export const tempDiffK = (r: Reading) => r.process_temp_k - r.air_temp_k;
export const strain = (r: Reading) => r.torque_nm * r.tool_wear_min;

export const OSF_LIMIT: Record<Reading["quality"], number> = { L: 11000, M: 12000, H: 13000 };

/** Which physical failure thresholds (AI4I rules) the reading currently violates. */
export function violations(r: Reading): string[] {
  const out: string[] = [];
  if (tempDiffK(r) < 8.6 && r.rpm < 1380) out.push("ΔT < 8.6 K at low rpm");
  const p = powerW(r);
  if (p < 3500 || p > 9000) out.push(`power ${(p / 1000).toFixed(1)} kW out of range`);
  if (strain(r) > OSF_LIMIT[r.quality]) out.push("strain over limit");
  if (r.tool_wear_min >= 200) out.push("tool past 200 min");
  return out;
}
