 
from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import os 
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from groq import Groq 
load_dotenv() 
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def analyser_reve(reve):
    
    prompt = f"""
    Tu es un expert en psychologie des rêves.

    Analyse ce rêve en 3 parties :
    1. Émotions
    2. Symboles
    3. Interprétation claire

    Rêve : {reve}
    """

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",  
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        return response.choices[0].message.content

    except Exception as e:
        return f"Erreur IA : {str(e)}"


app = Flask(__name__)
app.secret_key = "secret123"

DATABASE = "dreams.db"

@app.route("/", methods=["GET" , "POST"])
def index() :
    if request.method == "POST":
        reve = request.form["reve"]
        analyse = analyser_reve(reve)
        return render_template("index.html", analyse=analyse)
    return render_template("index.html")


def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dreams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            interpretation TEXT,
            is_public INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)

    conn.commit()
    conn.close()

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]

        hashed_password = generate_password_hash(password, method="pbkdf2:sha256")

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                "INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
                (username, email, hashed_password)
            )
            conn.commit()
            conn.close()
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            conn.close()
            return "Cet email existe déjà."

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect(url_for("dashboard"))
        else:
            return "Email ou mot de passe incorrect."

    return render_template("login.html")


@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM dreams WHERE user_id = ?", (session["user_id"],))
    dreams = cursor.fetchall()
    conn.close()

    return render_template("dashboard.html", dreams=dreams, username=session["username"])


@app.route("/add_dream", methods=["GET", "POST"])
def add_dream():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        title = request.form["title"]
        content = request.form["content"]
        is_public = 1 if request.form.get("is_public") == "on" else 0

        interpretation = analyser_reve(content)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO dreams (user_id, title, content, interpretation, is_public)
            VALUES (?, ?, ?, ?, ?)
        """, (session["user_id"], title, content, interpretation, is_public))
        conn.commit()
        dream_id = cursor.lastrowid
        conn.close()

        return redirect(url_for("result", dream_id=dream_id))

    return render_template("add_dream.html")


@app.route("/result/<int:dream_id>")
def result(dream_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM dreams WHERE id = ? AND user_id = ?",
        (dream_id, session["user_id"])
    )
    dream = cursor.fetchone()
    conn.close()

    if not dream:
        return "Rêve introuvable."

    return render_template("result.html", dream=dream)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
