# ScholaGro (Flask)

Production‑ready groceries e‑commerce (Flask + SQLAlchemy + Bootstrap 5).

## Features
- Cart with live quantity updates, save‑for‑later.
- Checkout with delivery fee by zone, coupon codes, special instructions.
- Orders with detail page, 5‑min cancel window, status logs timeline.
- Homepage merchandising: Daily Deals, New Arrivals, Top Selling, Flash Sales (countdown).
- Shop filters: search, nested categories, price min/max + slider, in‑stock, new, min rating, sort by price/rating/newest.
- Autosuggest search (hover + keyboard ↑/↓/Enter/Esc).
- Reviews support and rating filters.
- Payments: M‑Pesa STK push (Daraja) with callback; Admin payments log page.
- Admin: products, categories, banners, orders (status updates + email), payments.

## Setup
1) Create virtualenv and install deps
```
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
```

2) Configure environment
```
copy .env.example .env
```
Fill `.env` values for DB, SMTP and M‑Pesa (see below).

3) Initialize database
```
flask --app run.py db upgrade
```

4) Run
```
python run.py
```

## Configuration
Environment variables (see `.env.example`):
- SECRET_KEY
- DATABASE_URL (SQLite default: sqlite:///scholagro.db)
- SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, SMTP_SENDER
- MPESA_CONSUMER_KEY, MPESA_CONSUMER_SECRET, MPESA_SHORT_CODE, MPESA_PASSKEY
- MPESA_CALLBACK_URL (public HTTPS to /payments/mpesa/callback)
- MPESA_BASE_URL (optional, defaults to sandbox https://sandbox.safaricom.co.ke)

## M‑Pesa STK flow (Daraja)
- Start: `/payments/mpesa/start/<order_id>?phone=2547XXXXXXX` (phone optional if in profile).
- Callback: `POST /payments/mpesa/callback` (Daraja Body.stkCallback payload).
- On success: Payment marked paid, Order marked confirmed, email sent to customer.
- Admin: review at `/admin/payments` (filter by status, inspect raw payload).

## Notes
- Default dev DB is SQLite file `scholagro.db`.
- For production, use Postgres/MySQL and a real SMTP provider.
