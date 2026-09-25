# HDF-MAN — Heat Dissipation Failure: Cooling System Diagnosis

Document ID: HDF-MAN · Revision 4 · Applies to: CNC milling cells M-series
Owner: Plant Maintenance · Related: SAFE-SOP, ESC-PROC, SENS-REF, PWF-MAN

## 1. Scope

1.1 This manual covers failures caused by the machine failing to shed process heat (Heat Dissipation Failure, HDF).

1.2 The process zone must stay at least **8.6 K hotter than the ambient air** so that heat flows out through the coolant loop and the enclosure. When that gap collapses at low spindle speed, heat builds up in the spindle bearings and the workpiece.

## 2. Failure mechanism

2.1 Heat leaves the process zone by coolant flow, by the air moved by spindle rotation, and by conduction through the machine bed.

2.2 An HDF happens when **both** of these are true:
- the process-air temperature difference is **below 8.6 K**, and
- spindle speed is **below 1,380 rpm**.

2.3 At low speed there is little forced convection around the spindle. A small temperature difference means the ambient air can no longer absorb heat from the process zone. Together, these drive the spindle bearings towards thermal seizure.

2.4 Common root causes, most frequent first:
1. A clogged coolant filter or a low coolant level.
2. A failed or slow coolant pump.
3. Hot ambient air (for example, summer operation with the enclosure doors shut, or a failed HVAC unit nearby).
4. Chip build-up blocking the enclosure air vents.
5. Heat-exchanger fins fouled with oil mist.

## 3. Symptoms and evidence

3.1 **Primary indicator:** process temperature (SENS-REF Section 2.2) minus air temperature (SENS-REF Section 2.1) is below 8.6 K while spindle speed is below 1,380 rpm.

3.2 **Supporting evidence:**
- The air temperature is at the top of its normal range (above 302 K) and the process temperature has not risen with it.
- High torque at low speed, which is typical of roughing passes on hard material.
- Coolant flow warning on the HMI, or a coolant-level alarm.

3.3 If power is also out of range, check PWF-MAN first. A spindle drive fault can reduce speed and trigger an HDF as a knock-on effect.

## 4. Immediate response

4.1 Raise spindle speed above 1,400 rpm if the process allows it. This restores convective cooling within minutes and can prevent seizure.

4.2 If speed cannot be changed, press **Feed Hold** and let the spindle idle at 1,500 rpm with coolant on for 5 minutes.

4.3 Do not open the enclosure while coolant is spraying at operating temperature (SAFE-SOP Section 4.1).

## 5. Corrective maintenance

5.1 **Coolant level:** Check the sump sight glass. Top up to the MAX line with the approved coolant mix (6% concentrate), measured with a refractometer.

5.2 **Coolant filter:** Apply lockout/tagout on the coolant pump (SAFE-SOP Section 3.2). Swap the filter cartridge. A differential pressure above 0.8 bar across the filter means it is clogged.

5.3 **Pump check:** With the pump running, measure the flow at the nozzle manifold. Below 18 L/min, the pump or its inlet strainer needs service.

5.4 **Air path:** Clear chips from the enclosure vents and clean the heat-exchanger fins with low-pressure air (under 2 bar), blowing away from the operator.

5.5 **Ambient:** If the air temperature is above 303 K, open the cell doors between cycles or get HVAC checked (ESC-PROC Level 2, Facilities).

5.6 Run the machine for 15 minutes at production speed. Confirm the process-air temperature difference stays above 9.5 K before releasing the cell.

## 6. Prevention

6.1 Check the coolant concentration every shift and swap the filter weekly.

6.2 Avoid long low-speed roughing (below 1,380 rpm) on hot days without extra coolant flow.

## 7. Escalation

7.1 Escalate to Plant Maintenance (ESC-PROC Level 2) if the process-air difference does not recover within 15 minutes after Section 5.

7.2 Escalate to ESC-PROC Level 3 (stop the cell) if spindle bearing temperature exceeds 70 °C, or if there is a burning smell or smoke.
