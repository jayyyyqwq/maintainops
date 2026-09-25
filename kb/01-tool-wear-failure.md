# TWF-MAN — Tool Wear Failure: Diagnosis and Tool Replacement

Document ID: TWF-MAN · Revision 3 · Applies to: CNC milling cells M-series, product qualities L, M, H
Owner: Tooling Engineering · Related: SAFE-SOP, ESC-PROC, SENS-REF

## 1. Scope

1.1 This manual covers failures caused by the cutting tool reaching the end of its usable life (Tool Wear Failure, TWF).

1.2 A TWF is recorded when the tool breaks or is withdrawn after the machine's tool-wear counter has passed the replacement window. It applies to all spindle tools that the line's tool-life counter tracks.

## 2. Failure mechanism

2.1 Flank and crater wear build up with every minute of cutting. Past the end of its life the cutting edge chips, the cutting forces rise, and the tool fractures without warning.

2.2 On this line, tools are rated for **200 to 240 minutes** of cutting. A tool can fail at any point inside that window, so a failure cannot be predicted to the exact minute. Treat 200 minutes as the hard planning limit.

2.3 Wear is added according to product quality: H-quality jobs add 5 minutes of wear per job, M-quality 3 minutes and L-quality 2 minutes. H-quality batches therefore reach the window faster.

2.4 Tool wear is also the lever arm of overstrain (see OSF-MAN Section 2). A worn tool under high torque can fail by overstrain before it reaches the TWF window.

## 3. Symptoms and evidence

3.1 **Primary indicator:** the tool-wear counter (SENS-REF Section 2.5) reads 200 minutes or more.

3.2 **Secondary indicators:**
- Torque rises by more than 10% over the job baseline at an unchanged spindle speed.
- Surface finish gets worse, or burrs appear on the parts.
- An audible change in cutting noise, such as chatter or squeal.

3.3 Temperature readings are normally *not* affected by tool wear alone. A tool-wear alert combined with an abnormal process-air temperature difference should be investigated as a possible heat dissipation fault (HDF-MAN).

## 4. Immediate response

4.1 Let the current cut finish if the tool-wear reading is below 230 minutes and there is no abnormal noise. Otherwise, press **Feed Hold** straight away.

4.2 Do not restart the spindle with a tool that has passed 240 minutes of wear under any circumstances.

4.3 Apply lockout/tagout before touching the spindle or tool holder (SAFE-SOP Section 3).

## 5. Tool replacement procedure

5.1 Put the machine in Setup mode and retract the Z axis to the tool-change position.

5.2 Apply lockout/tagout (SAFE-SOP Section 3.2). Wait until the spindle is at a full stop, which is at least 10 seconds after the stop command.

5.3 Put on cut-resistant gloves (SAFE-SOP Section 2.1). Release the drawbar and remove the tool holder.

5.4 Inspect the tool holder taper for fretting or chips. If the taper is damaged, tag the holder "Do Not Use" and use a spare.

5.5 Fit a new tool from the tool crib, set the tool length offset with the tool presetter, and enter the new offset.

5.6 **Reset the tool-wear counter to 0 minutes** in the controller's tool table. If you skip this step, the counter keeps raising false TWF and OSF alerts.

5.7 Remove the lockout. Run the spindle warm-up cycle for 2 minutes at 1,500 rpm before cutting.

5.8 Cut one test part, measure its critical dimensions, and release the cell back to production.

## 6. Prevention

6.1 Plan tool changes at **180 minutes** of wear for L and M quality work and at **170 minutes** for H quality work.

6.2 Do not extend tool life to finish a batch. A broken tool costs more in scrapped parts and spindle damage than a new insert does.

6.3 Record every replacement in the maintenance log, with the wear reading at the time of the change.

## 7. Escalation

7.1 Escalate to Tooling Engineering (ESC-PROC Level 2) in any of these cases:
- the tool fails below 180 minutes of wear;
- two TWF events happen on the same machine within one shift;
- the tool holder or spindle taper is damaged.
