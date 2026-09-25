# RNF-MAN — Random and Unexplained Failures

Document ID: RNF-MAN · Revision 1 · Applies to: CNC milling cells M-series
Owner: Plant Maintenance · Related: ESC-PROC, SAFE-SOP, SENS-REF

## 1. Scope

1.1 This manual covers stoppages that no process parameter explains (Random Failure, RNF), and alerts where the sensor readings do not match any known failure pattern.

1.2 Random failures happen at about **0.1%** of operating cycles, regardless of temperature, speed, torque or tool wear. Sensor data cannot predict them.

## 2. Typical causes

2.1 Electrical transients: power dips, loose connectors, a failed relay.

2.2 Controller or PLC faults: watchdog timeouts, communication loss with the drive.

2.3 External events: a door interlock opened during the cycle, or an e-stop pressed by mistake.

2.4 Material defects: voids or inclusions in the workpiece that make the tool jump.

## 3. Diagnosis

3.1 First, rule out the known failure modes by checking the readings against the thresholds in SENS-REF Section 4. If a threshold has been crossed, use that failure manual instead.

3.2 Read the controller alarm history for the 10 minutes before the stop.

3.3 Check the door interlock and e-stop logs.

3.4 Inspect the workpiece for material defects at the point where the tool stopped.

## 4. Response

4.1 If no cause is found, restart once in single-block mode while watching the machine.

4.2 If the same unexplained stop happens twice within 24 hours, it is no longer random. Escalate (Section 5).

## 5. Escalation

5.1 Escalate to Plant Maintenance (ESC-PROC Level 2) on a second unexplained stop within 24 hours.

5.2 Record every RNF in the maintenance log so that patterns can be found over time.

## 6. Guidance for automated alerts

6.1 An automated risk alert with no failure-mode threshold crossed should be treated as **low confidence**. A technician must confirm it by visual inspection before any parts are replaced.
