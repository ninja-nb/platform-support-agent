---
doc_id: quota-006
title: Deploy rejected with QUOTA_EXCEEDED
service: deploy
tags: quotas, limits, deploy
audience: employee
status: current
updated: 2026-05-11
---

# Deploy rejected with QUOTA_EXCEEDED

The deploy is rejected immediately and the event log names the exhausted quota, for
example `vcpu` or `workers_per_environment`.

## Cause

The organization has reached a hard limit for the named resource. Unlike
`INSUFFICIENT_CAPACITY` (see `dep-003`), retrying or changing zone will never succeed,
because the rejection is an accounting decision rather than a scheduling one.

## Resolution

1. Read current consumption in the console under **Organization > Quotas**.
2. Reclaim first. Stopped-but-allocated environments continue to consume `vcpu` quota,
   and reclaiming an idle sandbox is usually faster than a quota increase.
3. If reclamation is not possible, file a quota increase. Standard turnaround is one
   business day; `vcpu` increases above 2,000 require capacity review and take longer.

## Escalate when

Console consumption does not match the sum of running environments, which indicates a
metering fault and needs the Platform Billing team.
