from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

from flask import Flask, flash, g, redirect, render_template, request, url_for

BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "swizbarberque.db"

app = Flask(__name__)
app.config["SECRET_KEY"] = "swizbarberque-secret-key"


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_error: Exception | None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    db = get_db()
    with closing(db.cursor()) as cursor:
        cursor.executescript(
            """
            CREATE TABLE IF NOT EXISTS rooms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                room_number TEXT NOT NULL UNIQUE,
                room_type TEXT NOT NULL,
                price_per_night REAL NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('available', 'maintenance', 'occupied'))
            );

            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guest_name TEXT NOT NULL,
                guest_email TEXT NOT NULL,
                phone TEXT NOT NULL,
                room_id INTEGER NOT NULL,
                check_in TEXT NOT NULL,
                check_out TEXT NOT NULL,
                guests INTEGER NOT NULL,
                special_request TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(room_id) REFERENCES rooms(id)
            );
            """
        )

        room_count = cursor.execute("SELECT COUNT(*) AS total FROM rooms").fetchone()["total"]
        if room_count == 0:
            cursor.executemany(
                """
                INSERT INTO rooms (room_number, room_type, price_per_night, status)
                VALUES (?, ?, ?, ?)
                """,
                [
                    ("101", "Standard", 5500, "available"),
                    ("102", "Deluxe", 7000, "available"),
                    ("201", "Executive", 9000, "available"),
                    ("301", "Suite", 12500, "maintenance"),
                ],
            )
    db.commit()


@app.before_request
def ensure_database() -> None:
    init_db()


@app.route("/")
def home():
    db = get_db()
    rooms = db.execute(
        """
        SELECT *
        FROM rooms
        ORDER BY room_number
        """
    ).fetchall()
    return render_template("index.html", rooms=rooms)


@app.route("/book", methods=["POST"])
def book_room():
    guest_name = request.form.get("guest_name", "").strip()
    guest_email = request.form.get("guest_email", "").strip()
    phone = request.form.get("phone", "").strip()
    room_id = request.form.get("room_id", "").strip()
    check_in = request.form.get("check_in", "").strip()
    check_out = request.form.get("check_out", "").strip()
    guests = request.form.get("guests", "").strip()
    special_request = request.form.get("special_request", "").strip()

    required_fields = [guest_name, guest_email, phone, room_id, check_in, check_out, guests]
    if any(not field for field in required_fields):
        flash("Please fill in all required booking details.", "error")
        return redirect(url_for("home"))

    try:
        room_id_int = int(room_id)
        guests_int = int(guests)
        check_in_date = datetime.strptime(check_in, "%Y-%m-%d")
        check_out_date = datetime.strptime(check_out, "%Y-%m-%d")
    except ValueError:
        flash("Invalid booking data provided.", "error")
        return redirect(url_for("home"))

    if check_out_date <= check_in_date:
        flash("Check-out date must be after check-in date.", "error")
        return redirect(url_for("home"))

    db = get_db()
    room = db.execute("SELECT * FROM rooms WHERE id = ?", (room_id_int,)).fetchone()
    if room is None:
        flash("Selected room was not found.", "error")
        return redirect(url_for("home"))

    if room["status"] != "available":
        flash("Selected room is currently not available.", "error")
        return redirect(url_for("home"))

    overlapping = db.execute(
        """
        SELECT id
        FROM bookings
        WHERE room_id = ?
          AND NOT (? <= check_in OR ? >= check_out)
        """,
        (room_id_int, check_out, check_in),
    ).fetchone()

    if overlapping is not None:
        flash("The room is already booked for the selected dates.", "error")
        return redirect(url_for("home"))

    db.execute(
        """
        INSERT INTO bookings (
            guest_name,
            guest_email,
            phone,
            room_id,
            check_in,
            check_out,
            guests,
            special_request,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            guest_name,
            guest_email,
            phone,
            room_id_int,
            check_in,
            check_out,
            guests_int,
            special_request,
            datetime.utcnow().isoformat(),
        ),
    )
    db.commit()
    flash("Booking submitted successfully. We look forward to hosting you at SwizBarberQue!", "success")
    return redirect(url_for("home"))


@app.route("/admin")
def admin_dashboard():
    db = get_db()
    rooms = db.execute("SELECT * FROM rooms ORDER BY room_number").fetchall()
    bookings = db.execute(
        """
        SELECT
            bookings.*,
            rooms.room_number,
            rooms.room_type,
            rooms.price_per_night
        FROM bookings
        JOIN rooms ON rooms.id = bookings.room_id
        ORDER BY bookings.created_at DESC
        """
    ).fetchall()

    stats = {
        "total_rooms": len(rooms),
        "available_rooms": sum(1 for room in rooms if room["status"] == "available"),
        "active_bookings": len(bookings),
        "estimated_revenue": sum(
            (
                datetime.strptime(booking["check_out"], "%Y-%m-%d")
                - datetime.strptime(booking["check_in"], "%Y-%m-%d")
            ).days
            * booking["price_per_night"]
            for booking in bookings
        ),
    }

    return render_template("admin.html", rooms=rooms, bookings=bookings, stats=stats)


@app.route("/admin/rooms", methods=["POST"])
def add_room():
    room_number = request.form.get("room_number", "").strip()
    room_type = request.form.get("room_type", "").strip()
    price = request.form.get("price_per_night", "").strip()
    status = request.form.get("status", "available").strip()

    if not room_number or not room_type or not price:
        flash("Room number, type and price are required.", "error")
        return redirect(url_for("admin_dashboard"))

    try:
        price_value = float(price)
    except ValueError:
        flash("Room price must be a valid number.", "error")
        return redirect(url_for("admin_dashboard"))

    db = get_db()
    try:
        db.execute(
            """
            INSERT INTO rooms (room_number, room_type, price_per_night, status)
            VALUES (?, ?, ?, ?)
            """,
            (room_number, room_type, price_value, status),
        )
        db.commit()
        flash("Room added successfully.", "success")
    except sqlite3.IntegrityError:
        flash("Room number already exists or invalid status.", "error")

    return redirect(url_for("admin_dashboard"))


@app.route("/admin/rooms/<int:room_id>/status", methods=["POST"])
def update_room_status(room_id: int):
    status = request.form.get("status", "").strip()
    if status not in {"available", "occupied", "maintenance"}:
        flash("Invalid room status.", "error")
        return redirect(url_for("admin_dashboard"))

    db = get_db()
    db.execute("UPDATE rooms SET status = ? WHERE id = ?", (status, room_id))
    db.commit()
    flash("Room status updated.", "success")
    return redirect(url_for("admin_dashboard"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
