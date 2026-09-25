# SENS-REF — Sensor and Derived Signal Reference

Document ID: SENS-REF · Revision 3 · Applies to: CNC milling cells M-series
Owner: Controls Engineering

## 1. Purpose

1.1 This sheet describes each signal the monitoring system collects, its normal operating range, and the failure modes each signal relates to.

## 2. Measured signals

2.1 **Air temperature [K]** — ambient temperature at the cell enclosure intake. Normal range 295–305 K, with slow drift through the day (standard deviation about 2 K). Related to: HDF.

2.2 **Process temperature [K]** — temperature at the spindle nose and coolant return. Normally the air temperature plus about 10 K (range 305–314 K). Related to: HDF.

2.3 **Rotational speed [rpm]** — spindle speed, from the spindle encoder. Typical range 1,170–2,900 rpm; 1,380–1,700 rpm is most common for production work. Related to: HDF, PWF.

2.4 **Torque [Nm]** — spindle torque, calculated from drive current. Normally distributed around 40 Nm (standard deviation about 10 Nm); values above 65 Nm are unusual. Related to: PWF, OSF.

2.5 **Tool wear [min]** — cumulative cutting minutes on the current tool, from the controller's tool table. Resets to 0 when a tool is changed. Related to: TWF, OSF.

2.6 **Product quality [L/M/H]** — quality variant of the current job. L is 50% of production, M 30% and H 20%. Sets the overstrain limit (OSF-MAN Section 2.2) and the wear rate (TWF-MAN Section 2.3).

## 3. Derived signals

3.1 **Temperature difference [K]** = process temperature − air temperature. Healthy is above 8.6 K. Below 8.6 K at low speed means heat dissipation failure (HDF-MAN Section 2.2).

3.2 **Mechanical power [W]** = torque × rpm × 2π / 60. Healthy is 3,500–9,000 W (PWF-MAN Section 2.1).

3.3 **Strain index [min·Nm]** = tool wear × torque. The limit depends on quality: 11,000 for L, 12,000 for M, 13,000 for H (OSF-MAN Section 2.2).

## 4. Failure-mode threshold summary

| Failure mode | Condition | Manual |
|---|---|---|
| TWF | tool wear between 200 and 240 min | TWF-MAN |
| HDF | temperature difference < 8.6 K **and** rpm < 1,380 | HDF-MAN |
| PWF | power < 3,500 W **or** > 9,000 W | PWF-MAN |
| OSF | strain index > 11,000 (L) / 12,000 (M) / 13,000 (H) | OSF-MAN |
| RNF | none of the above; random, about 0.1% | RNF-MAN |

## 5. Data quality

5.1 A temperature reading that does not change for more than 30 minutes points to a sensor fault. Check the sensor wiring before trusting any HDF alert.

5.2 A negative torque value, or an rpm reading above 3,000, is a sensor or drive fault, not a process condition.

## 6. Predictive model

6.1 The monitoring system uses a gradient-boosted tree model (XGBoost) that turns the signals above into a failure risk score between 0 and 1 and a most-likely failure mode.

6.2 A risk score at or above 0.5 raises a critical alert. A score from 0.25 up to 0.5 shows as a warning on the dashboard.

6.3 The model is a decision aid. Always confirm the failure mode against the thresholds in Section 4 before replacing parts.
