from flask import Flask, render_template, jsonify, request, send_file
import sqlite3
import csv
import io
import os
from pathlib import Path

# ====================
# CONFIGURATION
# ====================

# Use environment variable for database path (for cloud deployment)
DB_PATH = os.getenv("DATABASE_PATH", Path(__file__).parent / "tracker.db")
app = Flask(__name__, static_folder="static", template_folder="templates")

# Disable debug mode in production
app.config["DEBUG"] = os.getenv("FLASK_ENV") != "production"

# ====================
# DATABASE FUNCTIONS
# ====================

def get_db():
    """Connect to the SQLite database"""
    connection = sqlite3.connect(str(DB_PATH))
    connection.row_factory = sqlite3.Row
    return connection

def init_db():
    """Create the tasks table if it doesn't exist"""
    db = get_db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            day INTEGER,
            topic TEXT,
            completed INTEGER DEFAULT 0,
            notes TEXT
        )
    """)
    db.commit()
    db.close()

# Initialize database when app starts
init_db()

# ====================
# ROUTES
# ====================

@app.route("/")
def index():
    """Home page - serve the HTML file"""
    return render_template("index.html")

# ----- GET TASKS -----

@app.route("/api/tasks", methods=["GET"])
def get_tasks():
    """Get all tasks or filter by day"""
    day = request.args.get("day", type=int)
    db = get_db()
    
    if day:
        # Filter by specific day
        tasks = db.execute(
            "SELECT * FROM tasks WHERE day = ? ORDER BY id", 
            (day,)
        ).fetchall()
    else:
        # Get all tasks sorted by day
        tasks = db.execute(
            "SELECT * FROM tasks ORDER BY day, id"
        ).fetchall()
    
    db.close()
    
    # Convert rows to dictionaries and return as JSON
    return jsonify([dict(task) for task in tasks])

# ----- CREATE TASK -----

@app.route("/api/tasks", methods=["POST"])
def create_task():
    """Add a new task"""
    data = request.get_json()
    day = data.get("day")
    topic = data.get("topic", "").strip()
    notes = data.get("notes", "").strip()
    
    # Validate input
    if not day or not topic:
        return jsonify({"error": "Day and topic are required"}), 400
    
    # Insert into database
    db = get_db()
    cursor = db.execute(
        "INSERT INTO tasks (day, topic, notes) VALUES (?, ?, ?)",
        (day, topic, notes)
    )
    db.commit()
    task_id = cursor.lastrowid
    
    # Fetch and return the new task
    new_task = db.execute(
        "SELECT * FROM tasks WHERE id = ?", 
        (task_id,)
    ).fetchone()
    db.close()
    
    return jsonify(dict(new_task)), 201

# ----- UPDATE TASK -----

@app.route("/api/tasks/<int:task_id>", methods=["PUT"])
def update_task(task_id):
    """Update a task (topic, notes, or day)"""
    data = request.get_json()
    db = get_db()
    
    # Build dynamic SQL update
    updates = []
    values = []
    
    if "topic" in data and data["topic"]:
        updates.append("topic = ?")
        values.append(data["topic"])
    
    if "notes" in data and data["notes"]:
        updates.append("notes = ?")
        values.append(data["notes"])
    
    if "day" in data and data["day"]:
        updates.append("day = ?")
        values.append(data["day"])
    
    # Check if there's anything to update
    if not updates:
        return jsonify({"error": "Nothing to update"}), 400
    
    # Add task_id to values for WHERE clause
    values.append(task_id)
    
    # Execute update
    sql = f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?"
    db.execute(sql, values)
    db.commit()
    
    # Fetch updated task
    task = db.execute(
        "SELECT * FROM tasks WHERE id = ?", 
        (task_id,)
    ).fetchone()
    db.close()
    
    return jsonify(dict(task)) if task else ("", 404)

# ----- TOGGLE TASK -----

@app.route("/api/tasks/<int:task_id>/toggle", methods=["POST"])
def toggle_task(task_id):
    """Mark task as completed or uncompleted"""
    db = get_db()
    
    # Get current completion status
    task = db.execute(
        "SELECT completed FROM tasks WHERE id = ?", 
        (task_id,)
    ).fetchone()
    
    if not task:
        return ("", 404)
    
    # Toggle the status (0 -> 1 or 1 -> 0)
    new_status = 0 if task["completed"] else 1
    db.execute(
        "UPDATE tasks SET completed = ? WHERE id = ?", 
        (new_status, task_id)
    )
    db.commit()
    
    # Fetch and return updated task
    updated_task = db.execute(
        "SELECT * FROM tasks WHERE id = ?", 
        (task_id,)
    ).fetchone()
    db.close()
    
    return jsonify(dict(updated_task))

# ----- DELETE TASK -----

@app.route("/api/tasks/<int:task_id>", methods=["DELETE"])
def delete_task(task_id):
    """Delete a task"""
    db = get_db()
    db.execute(
        "DELETE FROM tasks WHERE id = ?", 
        (task_id,)
    )
    db.commit()
    db.close()
    
    return ("", 204)  # 204 = No Content (success)

# ----- EXPORT CSV -----

@app.route("/api/export.csv", methods=["GET"])
def export_csv():
    """Export all tasks as a CSV file"""
    db = get_db()
    tasks = db.execute(
        "SELECT * FROM tasks ORDER BY day, id"
    ).fetchall()
    db.close()
    
    # Create CSV in memory
    csv_file = io.StringIO()
    writer = csv.writer(csv_file)
    
    # Write header
    writer.writerow(["id", "day", "topic", "completed", "notes"])
    
    # Write task data
    for task in tasks:
        writer.writerow([
            task["id"], 
            task["day"], 
            task["topic"], 
            task["completed"], 
            task["notes"]
        ])
    
    # Convert to bytes and send
    csv_bytes = io.BytesIO(csv_file.getvalue().encode("utf-8"))
    return send_file(
        csv_bytes,
        mimetype="text/csv",
        as_attachment=True,
        download_name="study_tracker.csv"
    )

# ====================
# RUN APP
# ====================

if __name__ == "__main__":
    # Get port from environment variable or default to 5000
    port = int(os.getenv("PORT", 5000))
    
    # Get host - use 0.0.0.0 to allow external connections
    host = os.getenv("HOST", "0.0.0.0")
    
    # Determine if debug mode should be on
    debug = os.getenv("FLASK_ENV") != "production"
    
    # Run the app
    app.run(debug=debug, host=host, port=port)

