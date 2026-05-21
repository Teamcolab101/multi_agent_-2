
import os
import uuid
import datetime
import requests
from typing import Optional

# ✅ FIXED: No https:// here
FS_DOMAIN  = os.getenv("FRESHSERVICE_DOMAIN", "vamshika4.freshservice.com")
FS_API_KEY = os.getenv("FRESHSERVICE_API_KEY", "cHm6VFUFMaa30fYt77cY")

PRIORITY_MAP = {"low": 1, "medium": 2, "high": 3, "urgent": 4}

CATEGORY_MAP = {
    "hardware": "Hardware",
    "software": "Software",
    "network":  "Network",
    "access":   "Access Management",
    "email":    "Email & Communication",
    "vpn":      "VPN & Remote Access",
    "other":    "General IT Support",
}


def create_freshservice_ticket(
    subject: str,
    description: str,
    requester_email: str,
    category: str = "other",
    priority: str = "medium",
) -> dict:
    """
    Create a ticket in FreshService.
    Returns a dict with ticket details.
    """
    category_label = CATEGORY_MAP.get(category.lower(), "General IT Support")
    priority_num   = PRIORITY_MAP.get(priority.lower(), 2)

    if FS_API_KEY:
        return _real_ticket(subject, description, requester_email,
                            category_label, priority_num)
    else:
        return _demo_ticket(subject, description, requester_email,
                            category_label, priority)
    

# 🔥 REAL API CALL
def _real_ticket(subject, description, email, category, priority_num) -> dict:
    url = f"https://{FS_DOMAIN}/api/v2/tickets"

    payload = {
        "subject": subject,
        "description": description,
        "email": email,
        "priority": priority_num,
        "status": 2,   # Open
        "source": 2,   # Portal
        "category": category,
        "type": "Incident",
    }

    resp = requests.post(
        url,
        json=payload,
        auth=(FS_API_KEY, "X"),
        headers={"Content-Type": "application/json"},
        timeout=15,
    )

    if resp.status_code in (200, 201):
        data = resp.json().get("ticket", {})
        tid = data.get("id", 0)

        return {
            "success": True,
            "ticket_id": f"INC{tid:06d}",
            "freshservice_id": str(tid),

            # ✅ Proper ticket URL
            "url": f"https://{FS_DOMAIN}/helpdesk/tickets/{tid}",
            # If this doesn’t work, switch to:
            # "url": f"https://{FS_DOMAIN}/a/tickets/{tid}",

            "subject": subject,
            "category": category,
            "priority": priority_num,
            "demo": False,
        }

    else:
        raise RuntimeError(
            f"FreshService API error {resp.status_code}: {resp.text}"
        )


# 🎭 DEMO MODE
def _demo_ticket(subject, description, email, category, priority) -> dict:
    rand_id = str(uuid.uuid4())[:6].upper()
    ticket_id = f"INC{rand_id}"

    portal_url = f"https://{FS_DOMAIN}/helpdesk/tickets/{rand_id}"

    return {
        "success": True,
        "ticket_id": ticket_id,
        "freshservice_id": rand_id,
        "url": portal_url,
        "subject": subject,
        "category": category,
        "priority": priority,
        "created_at": datetime.datetime.utcnow().isoformat(),
        "demo": True,
    }


# 🧠 AUTO DETECT CATEGORY + PRIORITY
def guess_ticket_info(user_message: str) -> dict:
    msg = user_message.lower()

    # Category detection
    category = "other"
    if any(w in msg for w in ["laptop", "printer", "monitor", "keyboard", "hardware"]):
        category = "hardware"
    elif any(w in msg for w in ["software", "install", "app", "error", "bug"]):
        category = "software"
    elif any(w in msg for w in ["network", "wifi", "internet"]):
        category = "network"
    elif any(w in msg for w in ["login", "password", "access"]):
        category = "access"
    elif any(w in msg for w in ["email", "gmail", "outlook"]):
        category = "email"
    elif any(w in msg for w in ["vpn", "remote"]):
        category = "vpn"

    # Priority detection
    priority = "medium"
    if any(w in msg for w in ["urgent", "asap", "critical", "down"]):
        priority = "high"
    elif any(w in msg for w in ["minor", "low", "later"]):
        priority = "low"

    return {"category": category, "priority": priority}


# 📩 FORMAT RESPONSE (for Streamlit UI)
def format_ticket_response(ticket: dict, user_name: str) -> str:
    demo_note = (
        "\n\n> ⚠️ **Demo Mode** — No actual FreshService key configured."
        if ticket.get("demo") else ""
    )

    return f"""✅ **IT Ticket Created Successfully!**

| Field | Details |
|---|---|
| **Ticket ID** | `{ticket['ticket_id']}` |
| **Subject** | {ticket['subject']} |
| **Category** | {ticket['category']} |
| **Priority** | {str(ticket['priority']).title()} |
| **Status** | Open |
| **Requester** | {user_name} |

🔗 **[View Ticket]({ticket['url']})**

{demo_note}
"""
