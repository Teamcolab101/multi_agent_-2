import os
import re
import datetime
import operator
import sqlite3

from typing import TypedDict, Annotated, Literal

from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, END

from langchain_core.messages import (
    HumanMessage,
    SystemMessage
)

from utils.rag_engine import (
    search_policy,
    is_policy_question
)

from utils.database import (
    save_message,
    get_chat_history,
    save_ticket,
    get_latest_ticket,
    get_pending_leave_requests,
    approve_leave_request,
    apply_leave
)

DB_NAME = "hr_system.db"

# DATABASE

def init_db():

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS leave_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        leave_type TEXT,
        start_date TEXT,
        end_date TEXT,
        days INTEGER,
        reason TEXT,
        status TEXT
    )
    """)

    conn.commit()
    conn.close()

init_db()

# LLM

def _llm(temp=0.3):

    return ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=temp,
        groq_api_key=os.getenv("GROQ_API_KEY")
    )

# STATE

class AgentState(TypedDict):

    messages: Annotated[list, operator.add]

    user_query: str
    user_id: int
    user_name: str
    user_email: str
    user_role: str
    session_id: str

    intent: str
    current_agent: str

    ticket_data: dict
    final_response: str

    history: list

# INTENT CLASSIFIER

def intent_classifier(query: str) -> str:

    prompt = f"""
You are an AI intent classification engine for an HR + IT support assistant.

Analyze the user's message carefully and determine the MOST appropriate intent.

Possible intents:

- leave
- pending_leave
- approve_leave
- ticket_status
- it_ticket
- policy
- general

Intent meanings:

leave:
Employee wants leave, time off, vacation, sick leave,
or mentions future unavailability.

pending_leave:
Manager wants to see leave requests waiting for approval.

approve_leave:
Manager approves or rejects leave requests.

ticket_status:
User asks about the progress or status of a ticket.

it_ticket:
User reports technical/software/hardware/network/system issues.

policy:
Questions about HR rules, company policies, benefits,
salary, maternity, holidays, etc.

general:
Normal conversation or unrelated queries.

Instructions:
- Return ONLY ONE intent
- No explanations
- lowercase only

User message:
{query}
"""

    try:

        response = _llm(temp=0).invoke([
            HumanMessage(content=prompt)
        ])

        intent = response.content.strip().lower()

        valid_intents = [
            "leave",
            "pending_leave",
            "approve_leave",
            "ticket_status",
            "it_ticket",
            "policy",
            "general"
        ]

        if intent not in valid_intents:
            return "general"

        return intent

    except Exception as e:

        print("Intent classification error:", e)

        return "general"

# SUPERVISOR

def supervisor_node(state: AgentState):

    state["intent"] = intent_classifier(
        state["user_query"]
    )

    return state

# HR POLICY AGENT

def hr_policy_agent(state: AgentState):

    context = search_policy(
        state["user_query"]
    )

    prompt = f"""
You are an HR assistant.

Answer only using the HR policy context.

HR Policy Context:
{context}
"""

    resp = _llm().invoke([
        SystemMessage(content=prompt),
        HumanMessage(content=state["user_query"])
    ])

    state["final_response"] = resp.content
    state["current_agent"] = "hr"

    return state

# DATE EXTRACTION

def extract_dates(query: str):

    dates = re.findall(
        r"\d{2}-\d{2}-\d{4}",
        query
    )

    start_date = dates[0] if len(dates) > 0 else None
    end_date = dates[1] if len(dates) > 1 else start_date

    return start_date, end_date

# LEAVE AGENT

def leave_agent(state: AgentState):

    query = state["user_query"]
    user_name = state["user_name"]

    start_date, end_date = extract_dates(query)

    if not start_date:

        state["final_response"] = (
            "❌ Please provide leave date in DD-MM-YYYY format."
        )

        return state

    apply_leave(
        employee_name=user_name,
        start_date=start_date,
        end_date=end_date,
        reason=query
    )

    state["final_response"] = f"""
✅ Leave Request Submitted

Employee: {user_name}

Dates:
{start_date} → {end_date}

Status: Pending Approval
"""

    state["current_agent"] = "leave"

    return state

# MANAGER LEAVE AGENT

def manager_leave_agent(state: AgentState):

    query = state["user_query"].lower()

    if state["user_role"] != "manager":

        state["final_response"] = (
            "❌ Only managers can access leave approvals."
        )

        return state

    # VIEW PENDING LEAVES

    if state["intent"] == "pending_leave":

        requests = get_pending_leave_requests()

        if not requests:

            state["final_response"] = (
                "✅ No pending leave requests."
            )

            return state

        response = "📋 Pending Leave Requests\n\n"

        for r in requests:

            response += (
                f"ID: {r[0]}\n"
                f"User ID: {r[1]}\n"
                f"Leave Type: {r[2]}\n"
                f"Start Date: {r[3]}\n"
                f"End Date: {r[4]}\n"
                f"Days: {r[5]}\n"
                f"Reason: {r[6]}\n"
                f"Status: {r[7]}\n\n"
            )

        state["final_response"] = response
        state["current_agent"] = "manager_leave"

        return state

    # APPROVE LEAVE

    if state["intent"] == "approve_leave":

        numbers = re.findall(r"\d+", query)

        if not numbers:

            state["final_response"] = (
                "❌ Please provide leave ID."
            )

            return state

        leave_id = int(numbers[0])

        ok = approve_leave_request(leave_id)

        if ok:

            state["final_response"] = (
                f"✅ Leave request {leave_id} approved."
            )

        else:

            state["final_response"] = (
                "❌ Leave request not found."
            )

        state["current_agent"] = "manager_leave"

        return state

    return state

# TICKET STATUS

def get_ticket_status(ticket):

    created = ticket.get("created_at")

    if not created:
        return "Pending"

    if isinstance(created, str):

        created = datetime.datetime.fromisoformat(
            created
        )

    diff = (
        datetime.datetime.utcnow() - created
    ).total_seconds()

    if diff < 120:
        return "Pending"

    elif diff < 300:
        return "In Progress"

    return "Resolved"

# IT SUPPORT AGENT

def it_support_agent(state: AgentState):

    query = state["user_query"]

    if state["intent"] == "ticket_status":

        ticket = get_latest_ticket(
            state["user_id"]
        )

        if not ticket:

            state["final_response"] = (
                "❌ No ticket found."
            )

            return state

        status = get_ticket_status({
            "created_at": ticket.created_at.isoformat()
        })

        state["final_response"] = f"""
🎫 Ticket Status

ID: {ticket.ticket_id}

Status: {status}
"""

        state["current_agent"] = "it_support"

        return state

    ticket_id = (
        f"INC-{datetime.datetime.utcnow().strftime('%H%M%S')}"
    )

    save_ticket({
        "ticket_id": ticket_id,
        "user_id": state["user_id"],
        "issue": query,
        "status": "Open"
    })

    state["final_response"] = f"""
✅ Ticket Created

ID: {ticket_id}

Issue:
{query}
"""

    state["current_agent"] = "it_support"

    return state

# GENERAL AGENT

def general_agent(state: AgentState):

    resp = _llm().invoke([
        SystemMessage(
            content="You are a helpful assistant."
        ),
        HumanMessage(
            content=state["user_query"]
        )
    ])

    state["final_response"] = resp.content
    state["current_agent"] = "general"

    return state

# ROUTER

def router(state: AgentState) -> Literal[
    "hr_policy_agent",
    "leave_agent",
    "manager_leave_agent",
    "it_support_agent",
    "general_agent"
]:

    return {
        "policy": "hr_policy_agent",
        "leave": "leave_agent",
        "pending_leave": "manager_leave_agent",
        "approve_leave": "manager_leave_agent",
        "it_ticket": "it_support_agent",
        "ticket_status": "it_support_agent",
        "general": "general_agent"

    }.get(
        state["intent"],
        "general_agent"
    )

# BUILD GRAPH

def build_graph():

    g = StateGraph(AgentState)

    g.add_node("supervisor", supervisor_node)
    g.add_node("hr_policy_agent", hr_policy_agent)
    g.add_node("leave_agent", leave_agent)
    g.add_node("manager_leave_agent", manager_leave_agent)
    g.add_node("it_support_agent", it_support_agent)
    g.add_node("general_agent", general_agent)

    g.set_entry_point("supervisor")

    g.add_conditional_edges(
        "supervisor",
        router,
        {
            "hr_policy_agent": "hr_policy_agent",
            "leave_agent": "leave_agent",
            "manager_leave_agent": "manager_leave_agent",
            "it_support_agent": "it_support_agent",
            "general_agent": "general_agent",
        }
    )

    for node in [
        "hr_policy_agent",
        "leave_agent",
        "manager_leave_agent",
        "it_support_agent",
        "general_agent"
    ]:

        g.add_edge(node, END)

    return g.compile()

graph = build_graph()

hr_chatbot = graph

# PROCESS MESSAGE

def process_message(
    query,
    user_id,
    user_name,
    user_email,
    user_role,
    session_id
):

    history = get_chat_history(session_id)

    state = {
        "messages": [],
        "user_query": query,
        "user_id": user_id,
        "user_name": user_name,
        "user_email": user_email,
        "user_role": user_role,
        "session_id": session_id,
        "intent": "",
        "current_agent": "",
        "ticket_data": {},
        "final_response": "",
        "history": history
    }

    result = graph.invoke(state)

    save_message(session_id, "human", query)

    save_message(
        session_id,
        "ai",
        result["final_response"]
    )

    return {
        "response": result["final_response"]
    }