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
    Tu es une IA sympathique, naturelle et bienveillante qui aide 
    à comprendre les rêves.
    Analyse le rêve de façon claire, courte et agréable à lire.
    Ton style doit être cool, humain, rassurant, ludique et facile à comprendre.
    Important 
    - Ne fais pas une réponse trop longue.
    - Ne sois pas trop scientifique ni trop compliqué.
    - Ne dis pas que l'interprétation est une vérité absolue.
    - Donne une vraie analyse psychologique possible.
    - Utilise un ton doux et positif.
    - Ne propose pas de te poser d'autres questions.



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

@app.route("/")
def index():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return redirect(url_for("feed")) 

    


def get_db_connection():
    conn = sqlite3.connect('dreams.db')
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
    password TEXT NOT NULL,
    avatar TEXT DEFAULT 'avatar1.png'
)
""")
    try:
        cursor.execute(
            "ALTER TABLE users ADD COLUMN avatar TEXT DEFAULT 'avatar1.png' "
        )
    except sqlite3.OperationalError:
        pass 


    
    cursor.execute("""
CREATE TABLE IF NOT EXISTS dreams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    interpretation TEXT,
    is_public INTEGER DEFAULT 0,
    dream_type TEXT DEFAULT 'reve',
    FOREIGN KEY (user_id) REFERENCES users (id)
)
""")
    try:
        cursor.execute("""
        ALTER TABLE dreams
        ADD COLUMN dream_type TEXT DEFAULT 'reve'
    """)
    except sqlite3.OperationalError:
        pass 


    cursor.execute("""
    CREATE TABLE IF NOT EXISTS comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        dream_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        content TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (dream_id) REFERENCES dreams (id),
        FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)

    cursor.execute("""
CREATE TABLE IF NOT EXISTS replies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    comment_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    FOREIGN KEY(comment_id) REFERENCES comments(id),
    FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)

    cursor.execute("""
CREATE TABLE IF NOT EXISTS likes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dream_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    UNIQUE(dream_id, user_id)
        
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

        cursor.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,)
        )

        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]

            return redirect(url_for("feed"))

    return render_template("login.html")

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. On récupère proprement l'utilisateur connecté AVEC son avatar
    cursor.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],))
    user = cursor.fetchone()

    # 2. On récupère les rêves (SANS le JOIN risqué qui faisait planter)
    cursor.execute("""
        SELECT * FROM dreams
        WHERE user_id = ?
        ORDER BY id DESC
    """, (session["user_id"],))
    dreams = cursor.fetchall()

    # Récupérer les commentaires ok!!!!!
    cursor.execute("""
        SELECT comments.*, users.username
        FROM comments
        JOIN users ON comments.user_id = users.id
        ORDER BY comments.id DESC
    """)
    comments = cursor.fetchall()

    # Récupérer les réponses ok!!!!!
    cursor.execute("""
        SELECT replies.*, users.username
        FROM replies
        JOIN users ON replies.user_id = users.id
        ORDER BY replies.id ASC
    """)
    replies = cursor.fetchall()

    # Récupérer les likes ok!!!!!
    cursor.execute("""
        SELECT dream_id, COUNT(*) AS like_count 
        FROM likes
        GROUP BY dream_id
    """)
    likes_rows = cursor.fetchall()
    
    likes = {}
    for row in likes_rows: 
        likes[row["dream_id"]] = row["like_count"]

    cursor.execute("""
    SELECT COUNT(*) FROM dreams
    WHERE user_id = ? AND dream_type = 'reve'
    """, (session["user_id"],))
    total_reves = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT COUNT(*) FROM dreams
        WHERE user_id = ? AND dream_type = 'cauchemar'
    """, (session["user_id"],))
    total_cauchemars = cursor.fetchone()[0]
    
    conn.close()

    return render_template(
        "dashboard.html",
        dreams=dreams,
        comments=comments,
        replies=replies,
        likes=likes,
        username=session["username"],
        user=user,
        total_reves=total_reves,
        total_cauchemars=total_cauchemars
    )

@app.route("/add_dream", methods=["GET", "POST"])
def add_dream():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        title = request.form["title"]
        content = request.form["content"]
        is_public = 1 if request.form.get("is_public") == "on" else 0
        dream_type = request.form.get("dream_type", "reve")


        interpretation = analyser_reve(content)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO dreams (user_id, title, content, interpretation, is_public, dream_type)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (session["user_id"], title, content, interpretation, is_public, dream_type))
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

@app.route("/feed")
def feed():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT dreams.*, users.username, users.avatar
        FROM dreams
        JOIN users ON dreams.user_id = users.id
        WHERE dreams.is_public = 1
        ORDER BY dreams.id DESC
""")
    dreams = cursor.fetchall()

    cursor.execute("""
        SELECT comments.*, users.username
        FROM comments
        JOIN users ON comments.user_id = users.id
        ORDER BY comments.created_at ASC
    """)
    comments = cursor.fetchall()

    cursor.execute("""
        SELECT replies.*, users.username
        FROM replies
        JOIN users ON replies.user_id = users.id
        ORDER BY replies.id ASC
    """)
    replies = cursor.fetchall()

    cursor.execute("""
        SELECT dream_id, COUNT(*) AS like_count
        FROM likes
        GROUP BY dream_id
    """)
    likes_rows = cursor.fetchall()
    
    likes = {}
    for row in likes_rows: likes[row["dream_id"]] = row["like_count"]

    conn.close()

    return render_template(
        "feed.html",
        dreams=dreams,
        comments=comments,
        replies=replies,
        likes=likes,
    )


@app.route("/comment/<int:dream_id>", methods=["POST"])
def comment(dream_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    content = request.form["content"]

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO comments (dream_id, user_id, content)
        VALUES (?, ?, ?)
    """, (dream_id, session["user_id"], content))

    conn.commit()
    conn.close()

    return redirect(url_for("feed"))

@app.route("/delete_dream/<int:dream_id>", methods=["POST"])
def delete_dream(dream_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM comments WHERE dream_id = ?",
        (dream_id,)
    )

    cursor.execute(
        "DELETE FROM dreams WHERE id = ? AND user_id = ?",
        (dream_id, session["user_id"])
    )

    conn.commit()
    conn.close()

    return redirect(url_for("feed"))


@app.route("/delete_comment/<int:comment_id>", methods=["POST"])
def delete_comment(comment_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM comments WHERE id = ? AND user_id = ?",
        (comment_id, session["user_id"])
    )

    conn.commit()
    conn.close()

    return redirect(request.referrer or url_for("feed"))




@app.route("/reply/<int:comment_id>", methods=["POST"])
def reply(comment_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    content = request.form["content"]

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO replies (comment_id, user_id, content) VALUES (?, ?, ?)",
        (comment_id, session["user_id"], content)
    )
    conn.commit()
    conn.close()

    return redirect(request.referrer) 

@app.route("/like/<int:dream_id>", methods=["POST"])
def like_dream(dream_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM likes WHERE dream_id = ? AND user_id = ?",
        (dream_id, session["user_id"])
    )
    existing_like = cursor.fetchone()

    if existing_like:
        cursor.execute(
            "DELETE FROM likes WHERE dream_id = ? AND user_id = ?",
            (dream_id, session["user_id"])
        )
    else:
        cursor.execute(
            "INSERT INTO likes (dream_id, user_id) VALUES (?, ?)",
            (dream_id, session["user_id"])
        )

    conn.commit()
    conn.close()

    return redirect(request.referrer or url_for("feed"))

@app.route("/update_avatar", methods=["POST"])
def update_avatar():
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    new_avatar = request.form.get("avatar_name") 
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET avatar = ? WHERE id = ?", (new_avatar, session["user_id"]))
    conn.commit()
    conn.close()
    
    return redirect(url_for("dashboard"))



if __name__ == "__main__":

    init_db()
    app.run(debug=True)
