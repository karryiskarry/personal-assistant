---
name: household-planning
description: Guidelines for decomposing chore/household planning requests into room-by-room tasks.
---

# Household Planning Skill

You are utilizing the specialized `household-planning` skill. Use the following domain knowledge when planning household chores and apartment cleaning goals:

## 1. Goal Decomposition Principles
- Decompose vague cleaning goals (e.g. "Help me clean my apartment") room-by-room.
- Prioritize heavy-traffic and high-hygiene areas first:
  1. **Bathroom** (deep clean sink, toilet, tub, mirror)
  2. **Kitchen** (wipe countertops, clean stovetop, wash dishes, empty trash)
  3. **Living Room / Bedroom** (dust surfaces, organize, vacuum, make bed)
- Always ask clarifying questions before generating a plan if the user hasn't specified:
  - The number or types of rooms.
  - Their cleaning priority or focus areas.
  - Desired task cadences (weekly, biweekly, monthly).

## 2. Standard Cleaning Cadences & Chore Splits
- Recommend sensible frequencies for generated tasks:
  - **Daily**: Wash dishes, wipe kitchen counters, make bed.
  - **Weekly**: Vacuum floors, mop, clean bathroom toilet/sink, empty garbage.
  - **Biweekly**: Wash bedsheets, dust shelves/furniture, clean microwave.
  - **Monthly**: Deep clean oven, wash windows, clean baseboards, vacuum under furniture.

## 3. Creating Tasks
- Use the `create_task` tool to log each decomposed task into the SQLite database.
- Always set:
  - `tag` to `'chore'`
  - `source` to `'plan_generated'`
  - `due_date` to an appropriate YYYY-MM-DD date based on the layout of the plan.
  - `recurrence` (e.g. `'daily'`, `'weekly'`, `'biweekly'`, `'monthly'`, or None/empty string if no recurrence) based on the task cadence.
