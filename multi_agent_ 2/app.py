"""
ARIA – HR & IT Assistant
Final Stable Streamlit Frontend
"""

import os
import sys
import uuid
import traceback
import re

import streamlit as st

# ✅ PAGE CONFIG
st.set_page_config(
    page_title="ARIA Assistant",
    page_icon="🤖",
    layout="wide"
)

# ✅ PATH FIX
sys.path.insert(0, os.path.dirname(__file__))

# ✅ ENV
from dotenv import load_dotenv
load_dotenv()

# ─────────────────────────────────────────────
# IMPORTS
# ─────────────────────────────────────────────

from utils.database import (
    init_db,
    authenticate_user,
    get_latest_ticket,
    get_pending_leave_requests,
    approve_leave_request
)

from agents.graph import process_message

from agents.ticket_agent import (
    get_ticket_status,
    handle_ticket
)

# ─────────────────────────────────────────────
# INIT DB
# ─────────────────────────────────────────────

init_db()

# ─────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────

defaults = {
    "authenticated": False,
    "user": None,
    "chat_history": [],
    "session_id": str(uuid.uuid4())
}

for k, v in defaults.items():

    if k not in st.session_state:
        st.session_state[k] = v

# ─────────────────────────────────────────────
# UI CSS
# ─────────────────────────────────────────────

st.markdown("""
<style>

.stApp {
    background: linear-gradient(135deg, #0f172a, #1e293b);
    color: white;
}

.header {
    font-size: 30px;
    font-weight: 700;
    margin-bottom: 20px;
}

.user-bubble {
    background: #2563eb;
    padding: 14px;
    border-radius: 14px;
    margin-bottom: 12px;
    color: white;
}

.bot-bubble {
    background: #1e293b;
    padding: 14px;
    border-radius: 14px;
    margin-bottom: 12px;
    border: 1px solid #334155;
    color: white;
}

</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════
# LOGIN PAGE
# ═══════════════════════════════════════════════

def login_page():

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:

        st.markdown(
            "<div class='header'>🤖 ARIA Login</div>",
            unsafe_allow_html=True
        )

        uname = st.text_input("Username")

        pwd = st.text_input(
            "Password",
            type="password"
        )

        if st.button("Login"):

            user = authenticate_user(
                uname,
                pwd
            )

            if user:

                st.session_state.authenticated = True

                st.session_state.user = {
                    "id": user.id,
                    "full_name": getattr(
                        user,
                        "full_name",
                        user.username
                    ),
                    "email": user.email,
                    "role": user.role
                }

                st.rerun()

            else:
                st.error("❌ Invalid credentials")


# ═══════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════

def sidebar():

    user = st.session_state.user

    with st.sidebar:

        st.markdown("## 🤖 ARIA")

        st.markdown(f"""
👤 **{user['full_name']}**

📧 {user['email']}

🔑 Role: **{user['role']}**
""")

        if st.button("🆕 New Chat"):

            st.session_state.chat_history = []

            st.session_state.session_id = str(
                uuid.uuid4()
            )

            st.rerun()

        if st.button("🚪 Logout"):

            st.session_state.authenticated = False
            st.session_state.user = None

            st.rerun()


# ═══════════════════════════════════════════════
# MAIN APP
# ═══════════════════════════════════════════════

def main_app():

    sidebar()

    user = st.session_state.user

    st.markdown(
        "<div class='header'>💬 ARIA Assistant</div>",
        unsafe_allow_html=True
    )

    if not st.session_state.chat_history:

        st.info(
            "👋 Welcome! Ask me anything..."
        )

    # DISPLAY CHAT HISTORY

    for msg in st.session_state.chat_history:

        if msg["role"] == "user":

            st.markdown(
                f"""
<div class='user-bubble'>
{msg['content']}
</div>
""",
                unsafe_allow_html=True
            )

        else:

            st.markdown(
                msg["content"],
                unsafe_allow_html=True
            )

    # CHAT INPUT

    user_input = st.chat_input(
        "Type your message..."
    )

    if user_input:

        st.session_state.chat_history.append({
            "role": "user",
            "content": user_input
        })

        st.markdown(
            f"""
<div class='user-bubble'>
{user_input}
</div>
""",
            unsafe_allow_html=True
        )

        response = """
<div class='bot-bubble'>
⚠️ Something went wrong
</div>
"""

        try:

            with st.spinner("Processing..."):

                query = user_input.lower()

                it_keywords = [
                    "error",
                    "issue",
                    "not working",
                    "bug",
                    "problem",
                    "crash",
                    "login issue",
                    "ticket",
                    "system issue",
                    "network"
                ]

                # ═══════════════════════════════
                # 👨‍💼 MANAGER FEATURES
                # ═══════════════════════════════

                if user["role"] == "manager":

                    # 📋 SHOW LEAVE REQUESTS

                    if (
                        "pending leave" in query
                        or "leave requests" in query
                        or "show leave" in query
                    ):

                        requests = get_pending_leave_requests()

                        if not requests:

                            response = """
<div class='bot-bubble'>
✅ No pending leave requests
</div>
"""

                        else:

                            html = """
<div class='bot-bubble'>
<h3>📋 Pending Leave Requests</h3>
"""

                            # ✅ FIXED TUPLE ERROR HERE

                            for r in requests:

                                html += f"""
<p>
<b>ID:</b> {r[0]}<br>
<b>Employee:</b> {r[1]}<br>
<b>Start Date:</b> {r[2]}<br>
<b>End Date:</b> {r[3]}<br>
<b>Reason:</b> {r[4]}<br>
<b>Status:</b> {r[5]}
</p>
<hr>
"""

                            html += "</div>"

                            response = html

                    # ✅ APPROVE LEAVE

                    elif "approve leave" in query:

                        numbers = re.findall(
                            r"\d+",
                            query
                        )

                        if not numbers:

                            response = """
<div class='bot-bubble'>
❌ Please provide leave request ID

Example:
approve leave 1
</div>
"""

                        else:

                            leave_id = int(numbers[0])

                            ok = approve_leave_request(
                                leave_id
                            )

                            if ok:

                                response = f"""
<div class='bot-bubble'>
✅ Leave request {leave_id} approved
</div>
"""

                            else:

                                response = """
<div class='bot-bubble'>
❌ Leave request not found
</div>
"""

                    # 🎫 TICKET STATUS

                    elif "status" in query:

                        ticket = get_latest_ticket(
                            user["id"]
                        )

                        if not ticket:

                            response = """
<div class='bot-bubble'>
❌ No ticket found
</div>
"""

                        else:

                            status = get_ticket_status({
                                "created_at":
                                ticket.created_at
                            })

                            response = f"""
<div class='bot-bubble'>
<h3>🎫 Ticket Status</h3>

<p>
<b>ID:</b> {ticket.ticket_id}
</p>

<p>
<b>Status:</b> {status}
</p>

</div>
"""

                    # 💻 IT SUPPORT

                    elif any(
                        word in query
                        for word in it_keywords
                    ):

                        ticket = handle_ticket(
                            user_input,
                            user["email"],
                            user["id"]
                        )

                        if not ticket.get("success"):

                            response = f"""
<div class='bot-bubble'>
❌ Ticket creation failed

<br><br>

<small>
{ticket.get('error')}
</small>
</div>
"""

                        else:

                            response = f"""
<div class='bot-bubble'>

<h3>💻 IT Support</h3>

<p>✅ Ticket Created</p>

<p>
<b>ID:</b>
{ticket.get('ticket_id')}
</p>

<a href="{ticket.get('url', '#')}"
target="_blank">

🚀 Open Ticket

</a>

</div>
"""

                    # 🤖 CHATBOT

                    else:

                        result = process_message(
                            user_input,
                            user["id"],
                            user["full_name"],
                            user["email"],
                            user["role"],
                            st.session_state.session_id
                        )

                        final_text = (
                            result.get("response")
                            or result.get("final_response")
                            or "⚠️ No response generated"
                        )

                        response = f"""
<div class='bot-bubble'>
{final_text}
</div>
"""

                # ═══════════════════════════════
                # 👤 NORMAL USERS
                # ═══════════════════════════════

                else:

                    # 🎫 TICKET STATUS

                    if "status" in query:

                        ticket = get_latest_ticket(
                            user["id"]
                        )

                        if not ticket:

                            response = """
<div class='bot-bubble'>
❌ No ticket found
</div>
"""

                        else:

                            status = get_ticket_status({
                                "created_at":
                                ticket.created_at
                            })

                            response = f"""
<div class='bot-bubble'>

<h3>🎫 Ticket Status</h3>

<p>
<b>ID:</b>
{ticket.ticket_id}
</p>

<p>
<b>Status:</b>
{status}
</p>

</div>
"""

                    # 💻 IT SUPPORT

                    elif any(
                        word in query
                        for word in it_keywords
                    ):

                        ticket = handle_ticket(
                            user_input,
                            user["email"],
                            user["id"]
                        )

                        if not ticket.get("success"):

                            response = f"""
<div class='bot-bubble'>
❌ Ticket creation failed

<br><br>

<small>
{ticket.get('error')}
</small>
</div>
"""

                        else:

                            response = f"""
<div class='bot-bubble'>

<h3>💻 IT Support</h3>

<p>✅ Ticket Created</p>

<p>
<b>ID:</b>
{ticket.get('ticket_id')}
</p>

<a href="{ticket.get('url', '#')}"
target="_blank">

🚀 Open Ticket

</a>

</div>
"""

                    # 🤖 CHATBOT

                    else:

                        result = process_message(
                            user_input,
                            user["id"],
                            user["full_name"],
                            user["email"],
                            user["role"],
                            st.session_state.session_id
                        )

                        final_text = (
                            result.get("response")
                            or result.get("final_response")
                            or "⚠️ No response generated"
                        )

                        response = f"""
<div class='bot-bubble'>
{final_text}
</div>
"""

        except Exception as e:

            st.error(f"⚠️ Error: {str(e)}")

            st.text(
                traceback.format_exc()
            )

            response = """
<div class='bot-bubble'>
❌ Internal error occurred
</div>
"""

        # DISPLAY RESPONSE

        st.markdown(
            response,
            unsafe_allow_html=True
        )

        # SAVE CHAT

        st.session_state.chat_history.append({
            "role": "assistant",
            "content": response
        })


# ═══════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════

if st.session_state.authenticated:

    main_app()

else:

    login_page()