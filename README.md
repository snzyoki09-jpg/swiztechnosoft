# SwizBarberQue Hotel Website Management System

A full-featured Flask-powered hotel website and management system for **SwizBarberQue**, located in **Tononoka, Mombasa**.

## Features

- Public hotel landing page with room catalog.
- Real-time booking form with date-overlap validation.
- Admin dashboard for:
  - Room inventory and status updates.
  - New room creation.
  - Booking list with guest details.
  - Summary metrics (rooms, availability, bookings, estimated revenue).
- SQLite persistence (`swizbarberque.db`) auto-initialized on first request.

## Quick Start

1. Create and activate a virtual environment.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the application:
   ```bash
   python app.py
   ```
4. Open:
   - Guest site: `http://127.0.0.1:5000/`
   - Admin dashboard: `http://127.0.0.1:5000/admin`

## Default Seed Rooms

- Room 101 – Standard – KES 5,500
- Room 102 – Deluxe – KES 7,000
- Room 201 – Executive – KES 9,000
- Room 301 – Suite – Maintenance

