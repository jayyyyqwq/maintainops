# ESC-PROC — Maintenance Escalation Procedure

Document ID: ESC-PROC · Revision 2 · Applies to: all CNC milling cells
Owner: Maintenance Management

## 1. Purpose

1.1 This procedure defines who is told, and how fast, when a machine alert or failure happens.

## 2. Escalation levels

2.1 **Level 1 — Operator / cell technician.** Covers alerts that the procedures in the failure manuals can resolve within 30 minutes: tool changes, coolant top-ups and feed adjustments. Log the event, no call-out needed.

2.2 **Level 2 — Specialist team.** Call out within 1 hour when:
- the Level 1 fix did not clear the alert within 30 minutes;
- a failure manual says to escalate (for example TWF-MAN Section 7, HDF-MAN Section 7.1, PWF-MAN Section 7.1, OSF-MAN Section 7.1);
- the same failure mode repeats on one machine within a shift.

| Failure area | Level 2 team |
|---|---|
| Tooling, tool holders, strain | Tooling Engineering |
| Coolant, cooling, ambient | Plant Maintenance (with Facilities for HVAC) |
| Drives, motors, electrical | Electrical Maintenance |
| Unexplained / random | Plant Maintenance |

2.3 **Level 3 — Cell shutdown.** Stop the cell immediately, isolate it, and phone the shift manager when:
- there is smoke, a burning smell, arcing or fire;
- spindle vibration exceeds 2.8 mm/s RMS after a tool break (OSF-MAN Section 7.2);
- spindle bearing temperature exceeds 70 °C (HDF-MAN Section 7.2);
- anyone is injured, or a safety device has failed.

## 3. Communication

3.1 Automated MaintainOps alerts go to the maintenance distribution list by email. The on-shift technician acknowledges the alert on the dashboard within 15 minutes.

3.2 For Level 3, phone as well as email. Do not rely on email alone.

## 4. Records

4.1 Record every escalation with: machine ID, alert time, failure mode, readings at the time of the alert, actions taken, and time to resolution.

4.2 Maintenance management reviews Level 2 and Level 3 events every week to find repeat causes.
