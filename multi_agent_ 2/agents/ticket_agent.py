
import os
import uuid
import datetime
import requests

from utils.database import save_ticket

# ─────────────────────────────────────────────
# FRESHSERVICE CONFIG
# ─────────────────────────────────────────────

FS_DOMAIN = os.getenv(
    "FRESHSERVICE_DOMAIN",
    "vamshika4.freshservice.com"
)

FS_API_KEY = os.getenv("FRESHSERVICE_API_KEY")

# ─────────────────────────────────────────────
# CATEGORY + PRIORITY MAP
# ─────────────────────────────────────────────

CATEGORY_MAP = {
    "hardware": "Hardware",
    "software": "Software",
    "network": "Network",
    "other": "Other"
}

PRIORITY_MAP = {
    "low": 1,
    "medium": 2,
    "high": 3
}

# ─────────────────────────────────────────────
# MAIN HANDLER
# ─────────────────────────────────────────────

def handle_ticket(
    user_message: str,
    user_email: str,
    user_id: int
):

    category = "other"
    priority = "medium"

    ticket = create_ticket(
        user_message,
        user_email,
        category,
        priority
    )

    # ✅ SAVE TO DB
    if ticket.get("success"):

        save_ticket({
            "user_id": user_id,
            "ticket_id": ticket["ticket_id"],
            "freshservice_id": ticket.get("freshservice_id"),
            "subject": ticket["subject"],
            "description": user_message,
            "category": category,
            "priority": priority,
            "status": "Pending",
            "freshservice_url": ticket.get("url"),
            "created_at": ticket["created_at"]
        })

    return ticket

# ─────────────────────────────────────────────
# CREATE TICKET
# ─────────────────────────────────────────────

def create_ticket(
    subject,
    email,
    category,
    priority
):

    if FS_API_KEY:
        return real_ticket(
            subject,
            email,
            category,
            priority
        )

    return demo_ticket(
        subject,
        email,
        category,
        priority
    )

# ─────────────────────────────────────────────
# REAL FRESHSERVICE TICKET
# ─────────────────────────────────────────────

def real_ticket(
    subject,
    email,
    category,
    priority
):

    url = f"https://{FS_DOMAIN}/api/v2/tickets"

    payload = {
        "subject": subject,
        "description": subject,
        "email": email,

        # ✅ SAFE GET
        "priority": PRIORITY_MAP.get(priority, 2),

        "status": 2,

        # ✅ SAFE GET
        "category": CATEGORY_MAP.get(category, "Other"),

        "type": "Incident"
    }

    try:

        r = requests.post(
            url,
            json=payload,
            auth=(FS_API_KEY, "X")
        )

        if r.status_code in (200, 201):

            tid = r.json()["ticket"]["id"]

            return {
                "success": True,
                "ticket_id": f"INC{tid}",
                "freshservice_id": tid,
                "url": f"https://{FS_DOMAIN}/helpdesk/tickets/{tid}",
                "subject": subject,
                "created_at": datetime.datetime.utcnow().isoformat()
            }

        return {
            "success": False,
            "error": r.text
        }

    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }

# ─────────────────────────────────────────────
# DEMO TICKET
# ─────────────────────────────────────────────

def demo_ticket(
    subject,
    email,
    category,
    priority
):

    rid = str(uuid.uuid4())[:6]

    return {
        "success": True,
        "ticket_id": f"INC{rid}",
        "freshservice_id": rid,
        "url": f"https://{FS_DOMAIN}/helpdesk/tickets/{rid}",
        "subject": subject,
        "created_at": datetime.datetime.utcnow().isoformat()
    }

# ─────────────────────────────────────────────
# GET TICKET STATUS
# ─────────────────────────────────────────────

def get_ticket_status(ticket):

    created_at = ticket.get("created_at")

    if not created_at:
        return "Pending"

    # ✅ STRING → DATETIME
    if isinstance(created_at, str):

        created_at = datetime.datetime.fromisoformat(
            created_at
        )

    diff = (
        datetime.datetime.utcnow() - created_at
    ).total_seconds()

    if diff < 120:
        return "Pending"

    elif diff < 300:
        return "In Progress"

    return "Resolved"