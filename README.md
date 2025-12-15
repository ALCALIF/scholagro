# ScholaGro (Flask)

Production-ready groceries e-commerce (Flask + SQLAlchemy + Bootstrap 5).

## Features
- Cart with live quantity updates, save-for-later.
- Checkout with delivery fee by zone, coupon codes, special instructions.
- Orders with detail page, 5-min cancel window, status logs timeline.
- Homepage merchandising: Daily Deals, New Arrivals, Top Selling, Flash Sales (countdown).
- Shop filters: search, nested categories, price min/max + slider, in-stock, new, min rating, sort by price/rating/newest.
- Autosuggest search (hover + keyboard ↑/↓/Enter/Esc).
- Reviews support and rating filters.
- Payments: M-Pesa STK push (Daraja) with callback; Admin payments log page.
- Admin: products, categories, banners, orders (status updates + email), payments.

## Setup
1) Create virtualenv and install deps
2) For production, ensure `wsgi.py` exists (already included) and use Gunicorn or similar WSGI servers. The provided `Procfile` references `wsgi:app`.

### Celery & Redis
To use background tasks (emails, CSV import) and caching in production, install Redis and set `REDIS_URL` in environment, then run a Celery worker:

```powershell
# Example: run celery worker
celery -A celery_worker.celery worker --loglevel=info
```

### SocketIO
SocketIO uses `eventlet` in production; to run with gunicorn and eventlet:

```powershell
gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:8000 wsgi:app
```

### Stripe
 - Set `STRIPE_*` env vars.
 - Add your `STRIPE_WEBHOOK_SECRET` and configure endpoint `POST /payments/stripe/webhook` in Stripe console.

### Run tests
```powershell
pytest -q
```

### Database initialization

If you see errors like "no such table: products" when running locally, initialize the database and apply migrations before starting the app.

PowerShell (recommended):
```powershell
& .\.venv\Scripts\Activate.ps1
python .\scripts\init_db.py
```

This script tries to apply alembic migrations using Flask-Migrate. If it fails (for example, when the `migrations/` folder isn't configured or for lightweight development), it falls back to `db.create_all()` which creates tables directly (development-only).

If you prefer to run Flask-Migrate directly:
```powershell
set FLASK_APP=run.py
python -m flask db upgrade
```

Make sure `SQLALCHEMY_DATABASE_URI` is set (default is `sqlite:///scholagro.db`) either via `.env` or environment variables.

## New Dynamic Features
	- Optional Redis + Celery for background tasks (emails, CSV import, long-running jobs). Add `REDIS_URL` and `CELERY_` values in env.
	- SocketIO for real-time events (order status updates, notifications). Requires `flask-socketio` server worker (use eventlet/gunicorn worker-class).
	- Stripe integration skeleton included for card payments (test keys required). Update env `STRIPE_*` keys.
  
	Running with SocketIO & eventlet (production)
	- To run SocketIO in production, use eventlet or gevent worker-class for Gunicorn:
		`gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:8000 wsgi:app`;
	- Alternatively, use `socketio.run(app)` for development.
- Auto-updating mini-cart: cart count polling every 10 seconds and refreshing mini-cart content when opened.
- Live order updates: Order detail page polls for status updates and refreshes the timeline in near-real time.
- Notifications: Unread notifications are polled and displayed to users as toasts; they are marked as read after shown.
- Health endpoint: `GET /api/health` returns DB connectivity and basic health info.

