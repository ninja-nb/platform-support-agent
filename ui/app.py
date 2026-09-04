"""Support console: paste a ticket, pick a role, see citations and the action gate.

    make ui
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import streamlit as st

from psa.agent import run
from psa.config import FIXTURES_DIR
from psa.mcp_server import audit, call_tool
from psa.roles import EMPLOYEE, SRE

st.set_page_config(page_title="Meridian platform support", layout="wide")

USERS = {
    EMPLOYEE: "dana@meridiancloud.example",
    SRE: "oncall@meridiancloud.example",
}

BEHAVIOR_HELP = {
    "answer": "Grounded answer from the help center.",
    "refuse": "Not covered by the corpus. The agent declined to guess.",
    "escalate": "Matched an escalation condition in the runbook.",
    "deny": "The caller's role does not permit this.",
    "propose_action": "A gated action is waiting on human confirmation.",
    "create_ticket": "Filed a ticket instead of answering.",
    "ask": "Needs more evidence before it can answer.",
}

st.title("Meridian Cloud platform support")
st.caption(
    "Fictional company, synthetic corpus. Grounded answers, role-gated tools, "
    "human-confirmed actions."
)

with st.sidebar:
    st.header("Caller")
    role = st.radio("Role", [EMPLOYEE, SRE], format_func=str.upper)
    user = st.text_input("User", USERS[role])
    st.caption(
        "`employee` is read-only and scoped to its own tickets. "
        "`sre` may read any ticket and request a gated restart."
    )
    st.divider()
    st.header("Sample tickets")
    tickets = json.loads((FIXTURES_DIR / "tickets.json").read_text(encoding="utf-8"))
    for ticket in tickets:
        if st.button(f"{ticket['ticket_id']}: {ticket['subject']}", use_container_width=True):
            st.session_state["query"] = ticket["body"]

query = st.text_area("Ticket text or question", value=st.session_state.get("query", ""), height=140)

if st.button("Run agent", type="primary", disabled=not query.strip()):
    with st.spinner("Retrieving and reasoning..."):
        result = run(query, role=role, user=user)
    st.session_state["result"] = result

result = st.session_state.get("result")
if result:
    left, right = st.columns([3, 2])

    with left:
        st.subheader("Response")
        st.info(f"**{result.behavior}** — {BEHAVIOR_HELP.get(result.behavior, '')}")
        st.markdown(result.answer)

        if result.pending_confirmation:
            pending = result.pending_confirmation
            st.warning(
                f"**Confirmation required**\n\n"
                f"Action: `{pending['action']}` on `{pending['service']}` "
                f"in `{pending['environment']}`\n\n"
                f"Impact: {pending['impact']}\n\n"
                f"Reversible: {pending['reversible']}"
            )
            if st.button("Confirm and execute", type="primary"):
                executed = call_tool(
                    "restart_service",
                    {
                        "service": pending["service"],
                        "environment": pending["environment"],
                        "confirm_token": pending["confirm_token"],
                    },
                    role=role,
                    user=user,
                )
                st.success(f"Executed and audited: {executed}")

        for denial in result.denials:
            st.error(f"Permission denied: {denial}")

    with right:
        st.subheader("Citations")
        if result.citations:
            for doc_id in result.citations:
                st.markdown(f"- `{doc_id}`")
        else:
            st.caption("No citations. Expected when the agent refuses.")

        st.subheader("Tool calls")
        for turn in result.turns:
            icon = "x" if turn.error else "ok"
            with st.expander(f"[{icon}] {turn.tool}"):
                st.json(turn.args)
                st.json(turn.error or turn.result)

        st.subheader("Run")
        st.metric("Latency", f"{result.latency_ms} ms")
        st.metric("Cost", f"${result.usage.cost_usd:.5f}")

    st.divider()
    st.subheader("Audit log")
    st.caption("Every tool call, including denials and confirmation prompts.")
    st.dataframe(
        [
            {
                "ts": r.ts,
                "user": r.user,
                "role": r.role,
                "tool": r.tool,
                "outcome": r.outcome,
                "ms": r.latency_ms,
            }
            for r in reversed(audit.entries())
        ],
        use_container_width=True,
        hide_index=True,
    )
