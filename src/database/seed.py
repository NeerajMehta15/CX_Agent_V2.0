from datetime import datetime, timedelta

from src.database.connection import init_db, SessionLocal
from src.database.models import User, Order, Ticket, CannedResponse


def seed_data():
    init_db()
    db = SessionLocal()

    # Check if data already exists
    if db.query(User).first():
        print("Database already seeded.")
        db.close()
        return

    # Create users
    users = [
        User(name="Alice Johnson", email="alice@example.com", phone="+1-555-0101"),
        User(name="Bob Smith", email="bob@example.com", phone="+1-555-0102"),
        User(name="Carol Williams", email="carol@example.com", phone="+1-555-0103"),
    ]
    db.add_all(users)
    db.flush()

    # Create orders
    now = datetime.utcnow()
    orders = [
        Order(user_id=users[0].id, product="Wireless Headphones", amount=79.99, status="delivered",
              created_at=now - timedelta(days=10)),
        Order(user_id=users[0].id, product="Phone Case", amount=19.99, status="shipped",
              created_at=now - timedelta(days=2)),
        Order(user_id=users[1].id, product="Laptop Stand", amount=49.99, status="pending",
              created_at=now - timedelta(days=1)),
        Order(user_id=users[1].id, product="USB-C Hub", amount=34.99, status="delivered",
              created_at=now - timedelta(days=15)),
        Order(user_id=users[2].id, product="Mechanical Keyboard", amount=129.99, status="shipped",
              created_at=now - timedelta(days=3)),
    ]
    db.add_all(orders)

    # Create tickets
    tickets = [
        Ticket(user_id=users[0].id, subject="Headphones not charging",
               description="My wireless headphones stopped charging after a week of use.",
               status="open", priority="high"),
        Ticket(user_id=users[1].id, subject="Order not received",
               description="It's been over a week and I haven't received my laptop stand.",
               status="in_progress", priority="medium", assigned_to="Support Team"),
        Ticket(user_id=users[2].id, subject="Wrong item received",
               description="I ordered a mechanical keyboard but received a regular one.",
               status="open", priority="high"),
    ]
    db.add_all(tickets)

    # Create canned responses
    canned_responses = [
        CannedResponse(
            shortcut="/greet",
            title="Greeting",
            content="Hello! Thank you for contacting us. How can I help you today?",
            category="greeting",
        ),
        CannedResponse(
            shortcut="/thanks",
            title="Thank You",
            content="Thank you for your patience. Is there anything else I can help you with?",
            category="greeting",
        ),
        CannedResponse(
            shortcut="/refund",
            title="Refund Process",
            content="I understand you'd like a refund. I'll initiate the refund process for you right away. You should see the amount credited to your original payment method within 5-7 business days.",
            category="refund",
        ),
        CannedResponse(
            shortcut="/shipping",
            title="Shipping Status",
            content="Let me check the shipping status for your order. Our standard shipping typically takes 3-5 business days. I'll look up the tracking information for you.",
            category="shipping",
        ),
        CannedResponse(
            shortcut="/escalate",
            title="Escalation",
            content="I understand this is a complex issue. Let me escalate this to our specialized team who can provide more detailed assistance. They will reach out to you within 24 hours.",
            category="support",
        ),
        CannedResponse(
            shortcut="/close",
            title="Closing",
            content="Thank you for contacting us today. If you have any more questions in the future, don't hesitate to reach out. Have a great day!",
            category="greeting",
        ),
    ]
    db.add_all(canned_responses)

    db.commit()
    db.close()
    print("Database seeded successfully with demo data.")


if __name__ == "__main__":
    seed_data()
