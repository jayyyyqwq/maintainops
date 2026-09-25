# OSF-MAN — Overstrain Failure: Tool and Spindle Overload

Document ID: OSF-MAN · Revision 3 · Applies to: CNC milling cells M-series
Owner: Tooling Engineering · Related: TWF-MAN, PWF-MAN, SAFE-SOP, ESC-PROC, SENS-REF

## 1. Scope

1.1 This manual covers failures caused by a worn tool carrying too much torque (Overstrain Failure, OSF).

## 2. Failure mechanism

2.1 A worn cutting edge concentrates stress. The load a tool can survive falls as its wear rises, so the product of **tool wear × torque** (the strain index) is what predicts overstrain.

2.2 The strain index limits depend on product quality:

| Product quality | Strain index limit (min·Nm) |
|---|---|
| L | 11,000 |
| M | 12,000 |
| H | 13,000 |

2.3 An OSF happens when the strain index exceeds the limit for the current product quality. The tool or tool holder breaks, and the spindle bearings may be damaged by shock loading.

2.4 OSF usually happens in the late part of tool life (150–220 minutes) during heavy cuts. That makes it different from TWF, which depends on wear alone (TWF-MAN Section 2.2).

## 3. Symptoms and evidence

3.1 **Primary indicator:** tool wear (SENS-REF Section 2.5) × torque (SENS-REF Section 2.4) exceeds the limit in Section 2.2.

3.2 **Supporting evidence:**
- Torque above 55 Nm on a tool with more than 180 minutes of wear.
- Spindle speed pulled below 1,400 rpm by the cutting load.
- Chatter marks on the part, or vibration alarms.

3.3 Normal power alongside a high strain index is typical of OSF. Power out of range points to PWF (PWF-MAN).

## 4. Immediate response

4.1 Press **Feed Hold** straight away. The tool has little fatigue margin left, and a break can throw fragments.

4.2 Keep people clear of the enclosure window line until the spindle has stopped (SAFE-SOP Section 4.2).

## 5. Corrective maintenance

5.1 Apply lockout/tagout (SAFE-SOP Section 3.2).

5.2 Replace the tool following TWF-MAN Section 5, including resetting the wear counter (TWF-MAN Section 5.6).

5.3 Inspect the tool holder for cracks around the collet or pull stud. Throw away any holder that shows cracks.

5.4 **Spindle check after a tool break:** Rotate the spindle by hand, with lockout still applied, and feel for roughness. Run the spindle vibration check at 1,500 rpm. If vibration exceeds 2.8 mm/s RMS, escalate (Section 7.2).

5.5 Change the program so the heavy cuts happen early in tool life, or lower the depth of cut so torque stays below 50 Nm on tools with more than 150 minutes of wear.

5.6 Run a test part and check dimensions before releasing the cell.

## 6. Prevention

6.1 Set a controller alarm when the strain index reaches 85% of the limit for the product quality: 9,350 for L, 10,200 for M and 11,050 for H.

6.2 Schedule L-quality heavy roughing onto fresh tools, because L has the lowest strain limit.

## 7. Escalation

7.1 Escalate to Tooling Engineering (ESC-PROC Level 2) after any OSF tool break.

7.2 Escalate to ESC-PROC Level 3 if spindle vibration exceeds 2.8 mm/s RMS after a break. The cell stays down until the spindle has been inspected.
