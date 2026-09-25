# PWF-MAN — Power Failure: Spindle Drive and Load Diagnosis

Document ID: PWF-MAN · Revision 2 · Applies to: CNC milling cells M-series
Owner: Electrical Maintenance · Related: SAFE-SOP, ESC-PROC, SENS-REF, OSF-MAN

## 1. Scope

1.1 This manual covers failures caused by the spindle running outside its safe mechanical power envelope (Power Failure, PWF).

1.2 Mechanical power is calculated from torque and speed: **P [W] = torque [Nm] × rotational speed [rpm] × 2π / 60**.

## 2. Failure mechanism

2.1 The spindle drive is rated for a continuous mechanical power of **3,500 W to 9,000 W**. A PWF happens when power leaves that range in either direction.

2.2 **Over-power (above 9,000 W):** high torque at moderate or high speed overloads the drive and motor windings. The drive trips on overcurrent, or the motor overheats. Typical causes:
- a feed rate or depth of cut set too high in the CNC program;
- a blunt tool, which raises the cutting force (see TWF-MAN Section 3.2);
- the wrong material loaded (harder than the program assumes).

2.3 **Under-power (below 3,500 W):** very low torque at high speed usually means the tool is not cutting properly (air cutting, a slipping tool holder) or the drive is unstable, and the controller aborts the job. Typical causes:
- tool pull-out, or a slipping drawbar;
- a worn spindle belt (belt-driven variants);
- a drive parameter fault.

## 3. Symptoms and evidence

3.1 **Primary indicator:** the calculated power (SENS-REF Section 3.2) is outside 3,500–9,000 W.

3.2 **Over-power evidence:** torque above about 65 Nm at speeds above 1,300 rpm, a spindle load meter above 110%, and drive overcurrent warnings.

3.3 **Under-power evidence:** torque below about 15 Nm at speeds above 2,200 rpm, and no chips being produced.

3.4 Torque that is high at low speed with a worn tool points to overstrain. Check OSF-MAN Section 3 before concluding PWF.

## 4. Immediate response

4.1 Press **Feed Hold**. On over-power, lower the feed override to 50% before resuming. Do not keep cutting above 100% spindle load.

4.2 If the drive has already tripped, do **not** reset it more than once. Repeated resets on an overcurrent fault can damage the drive's power stage.

## 5. Corrective maintenance

5.1 **Program check:** Compare the feed rate and depth of cut against the process sheet for the material. Reduce feed by 20% and test.

5.2 **Tool check:** Inspect the cutting edge. Replace the tool if it is worn (TWF-MAN Section 5).

5.3 **Tool holder and drawbar:** Apply lockout/tagout (SAFE-SOP Section 3.2). Check the drawbar clamping force with the force gauge. It must be at least 18 kN.

5.4 **Drive diagnostics (Electrical Maintenance only):** Read the drive fault log. Check the motor insulation resistance, which must be above 100 MΩ at 500 V DC. Only qualified electricians may open the drive cabinet (SAFE-SOP Section 5).

5.5 Run a test cut at 80% feed. Confirm power stays between 4,000 and 8,500 W throughout the cycle.

## 6. Prevention

6.1 Use the CAM power-limit check when programming new parts, and keep the programmed peak power under 8,000 W.

6.2 Check drawbar force monthly.

## 7. Escalation

7.1 Escalate to Electrical Maintenance (ESC-PROC Level 2) for any drive fault code, or if power is out of range with a correct program and tool.

7.2 Escalate to ESC-PROC Level 3 if you see a burning smell, visible arcing or smoke from the drive cabinet. Isolate the cell at the main switch.
