from flask import (Flask, render_template, request, redirect,
                   url_for, session, flash, jsonify, abort)
import sqlite3, os, hashlib, secrets, re
from datetime import datetime, timedelta
from functools import wraps
from werkzeug.utils import secure_filename
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "urcostumedits-super-secret-2025")
DB = "orders.db"

# ─── UPLOAD SETTINGS ───────────────────────────────────────────────────────
UPLOAD_FOLDER   = os.path.join("static", "images")
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def save_image(file_field_name):
    """Save an uploaded image and return its filename, or '' on failure."""
    f = request.files.get(file_field_name)
    if not f or f.filename == "":
        return ""
    if not allowed_file(f.filename):
        return ""
    filename = secure_filename(f.filename)
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    f.save(os.path.join(UPLOAD_FOLDER, filename))
    return filename

# ─── EMAIL ─────────────────────────────────────────────────────────────────
MAIL_SENDER      = "urcoustomedits152@gmail.com"
MAIL_PASSWORD    = "ogfyovjbghvlnsep"
MAIL_SENDER_NAME = "UrCostome Edit"


def send_reset_email(to_email: str, reset_url: str) -> bool:
    subject = "Reset your UrCostome Edit password"

    text_body = f"""Hi there,

We received a request to reset the password for your UrCostome Edit account.

Click the link below to set a new password:
{reset_url}

This link expires in 1 hour.
If you didn't request this, you can safely ignore this email.

— UrCostome Edit 🧶
"""

    html_body = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
  body  {{ font-family: Arial, sans-serif; background: #fdf6f0; margin: 0; padding: 0; }}
  .wrap {{ max-width: 520px; margin: 40px auto; background: #ffffff;
           border-radius: 16px; overflow: hidden;
           box-shadow: 0 8px 30px rgba(92,61,46,.12); }}
  .header {{ background: linear-gradient(135deg, #5c3d2e 0%, #3d1f10 100%);
             padding: 36px 40px; text-align: center; }}
  .header h1 {{ font-family: Georgia, serif; color: #ffffff;
                font-size: 1.5rem; margin: 0 0 6px; }}
  .header p  {{ color: rgba(255,255,255,.6); font-size: .85rem; margin: 0; }}
  .body  {{ padding: 40px; }}
  .body p {{ color: #5c3d2e; font-size: .93rem; line-height: 1.75;
             margin: 0 0 20px; }}
  .btn   {{ display: block; width: fit-content; margin: 0 auto 28px;
            background: linear-gradient(135deg, #e8776a, #d4564a);
            color: #ffffff; text-decoration: none;
            padding: 14px 40px; border-radius: 10px;
            font-size: .95rem; font-weight: 600;
            box-shadow: 0 4px 16px rgba(232,119,106,.4); }}
  .note  {{ font-size: .82rem !important; color: #9e8070 !important; }}
  .url   {{ color: #e8776a; word-break: break-all; font-size: .82rem; }}
  .footer {{ background: #f5ece3; padding: 20px 40px; text-align: center;
             font-size: .78rem; color: #9e8070; border-top: 1px solid #e8d8cc; }}
</style>
</head>
<body>
<div class="wrap">

  <div class="header">
    <h1>UrCostome Edit 🧶</h1>
    <p>Handmade with love &amp; yarn</p>
  </div>

  <div class="body">
    <p>Hi there,</p>
    <p>
      We received a request to reset the password for your
      <strong>UrCostome Edit</strong> account.
      Click the button below to choose a new password:
    </p>

    <a class="btn" href="{reset_url}">Reset My Password →</a>

    <p class="note">
      ⏱ This link expires in <strong>1 hour</strong>.<br>
      If you didn't request a password reset, you can safely ignore this
      email — your password will not change.
    </p>

    <p class="note">
      Button not working? Copy and paste this URL into your browser:<br>
      <a class="url" href="{reset_url}">{reset_url}</a>
    </p>
  </div>

  <div class="footer">
    © UrCostome Edit &nbsp;•&nbsp; Badlapur, Maharashtra<br>
    <a href="https://www.instagram.com/_urcustomedits_"
       style="color:#e8776a;text-decoration:none;">@_urcustomedits_</a>
  </div>

</div>
</body>
</html>"""

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"{MAIL_SENDER_NAME} <{MAIL_SENDER}>"
        msg["To"]      = to_email

        msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(MAIL_SENDER, MAIL_PASSWORD)
            server.sendmail(MAIL_SENDER, to_email, msg.as_string())

        print(f"[EMAIL] Reset email sent to {to_email}")
        return True

    except smtplib.SMTPAuthenticationError as e:
        print(f"[EMAIL ERROR] Auth failed - check app password: {e}")
        return False
    except Exception as e:
        print(f"[EMAIL ERROR] {type(e).__name__}: {e}")
        return False

# ─── ADMIN ACCOUNTS (username: password) ───────────────────────────────────
ADMINS = {
    "admin":  "Admin@1234",
    "owner":  "Owner@5678",
    "manager":"Manager@9012"
}

# ─── DEFAULT PRODUCTS (used only on first init) ────────────────────────────
DEFAULT_PRODUCTS = [
    {"id":"heart",    "name":"Heart Crochet Keychain",    "image":"heart.jpeg",    "price":99,  "description":"A cute handmade crochet heart keychain with soft yarn texture and a warm aesthetic finish.","criteria":"Choose any heart colour|Initial/name can be added|Keyring included|Gift packing available","best_for":"Couples, best friends, birthdays, hampers","category":"Keychains","stock":50},
    {"id":"bow",      "name":"Bow Crochet Keychain",      "image":"bow.jpeg",      "price":99,  "description":"A soft pink bow crochet keychain with a coquette, cute and premium handmade look.","criteria":"Colour can be customised|Small/medium size available|Keyring included|Bulk orders available","best_for":"Pouches, bags, birthday hampers, girly gifts","category":"Keychains","stock":50},
    {"id":"evil-eye", "name":"Evil Eye Heart Keychain",   "image":"evil-eye.jpeg", "price":120, "description":"A blue evil-eye inspired heart crochet keychain with bold handmade detailing.","criteria":"Evil eye or plain heart style|Colour shades can be changed|Keyring included|Gift packing available","best_for":"Bag charms, bestie gifts, protection-themed gifts","category":"Keychains","stock":30},
    {"id":"letter",   "name":"Alphabet Crochet Keychain", "image":"letter.jpeg",   "price":120, "description":"A personalised crochet alphabet keychain made in your selected letter and colour combination.","criteria":"Any alphabet A-Z|Two-colour combination|Name tag can be added|Bulk orders accepted","best_for":"School bags, farewell gifts, class orders, personal gifts","category":"Personalised","stock":40},
    {"id":"cross",    "name":"Cross Crochet Keychain",    "image":"cross.jpeg",    "price":99,  "description":"A simple and elegant handmade crochet cross keychain in warm cream and brown tones.","criteria":"Colour combination can be selected|Small/medium size|Keyring included|Gift packing available","best_for":"Faith gifts, Christmas gifts, personal keychains","category":"Keychains","stock":35},
]

# ─── HELPERS ───────────────────────────────────────────────────────────────
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def get_db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    con = get_db()
    con.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT,
            password TEXT NOT NULL,
            reset_token TEXT,
            reset_expiry TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            is_active INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS products (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            image TEXT,
            image2 TEXT,
            price INTEGER NOT NULL,
            description TEXT,
            criteria TEXT,
            best_for TEXT,
            category TEXT DEFAULT 'General',
            stock INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT,
            user_id INTEGER,
            customer_name TEXT,
            contact TEXT,
            email TEXT,
            address TEXT,
            product_id TEXT,
            product_name TEXT,
            quantity INTEGER,
            unit_price INTEGER,
            total_price INTEGER,
            details TEXT,
            status TEXT DEFAULT 'New',
            tracking_note TEXT,
            updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            product_id TEXT,
            rating INTEGER,
            comment TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS wishlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            product_id TEXT,
            added_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)
    # Seed products if empty
    existing = con.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    if existing == 0:
        for p in DEFAULT_PRODUCTS:
            con.execute(
                "INSERT OR IGNORE INTO products(id,name,image,price,description,criteria,best_for,category,stock) VALUES(?,?,?,?,?,?,?,?,?)",
                (p["id"], p["name"], p["image"], p["price"], p["description"],
                 p["criteria"], p["best_for"], p["category"], p["stock"])
            )
    con.commit()

    # ── Migrations ──────────────────────────────────────────────────────────
    existing_cols = [row[1] for row in con.execute("PRAGMA table_info(orders)").fetchall()]
    if "user_id" not in existing_cols:
        con.execute("ALTER TABLE orders ADD COLUMN user_id INTEGER")
        con.commit()

    prod_cols = [row[1] for row in con.execute("PRAGMA table_info(products)").fetchall()]
    if "image2" not in prod_cols:
        con.execute("ALTER TABLE products ADD COLUMN image2 TEXT")
        con.commit()

    con.close()

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("auth", next=request.url))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("auth"))
        return f(*args, **kwargs)
    return decorated

# ─── PUBLIC ROUTES ─────────────────────────────────────────────────────────
@app.route("/")
def home():
    con = get_db()
    featured = con.execute(
        "SELECT * FROM products WHERE is_active=1 ORDER BY RANDOM() LIMIT 4"
    ).fetchall()
    con.close()
    return render_template("home.html", featured=featured)

@app.route("/products")
def products():
    category = request.args.get("category", "")
    search = request.args.get("q", "")
    con = get_db()
    query = "SELECT * FROM products WHERE is_active=1"
    params = []
    if category:
        query += " AND category=?"
        params.append(category)
    if search:
        query += " AND (name LIKE ? OR description LIKE ?)"
        params += [f"%{search}%", f"%{search}%"]
    items = con.execute(query, params).fetchall()
    categories = con.execute("SELECT DISTINCT category FROM products WHERE is_active=1").fetchall()
    con.close()
    return render_template("products.html", products=items,
                           categories=categories, selected_cat=category, search=search)

@app.route("/product/<pid>")
def product(pid):
    con = get_db()
    p = con.execute("SELECT * FROM products WHERE id=? AND is_active=1", (pid,)).fetchone()
    if not p:
        abort(404)
    reviews = con.execute(
        "SELECT r.*, u.name as user_name FROM reviews r JOIN users u ON r.user_id=u.id WHERE r.product_id=? ORDER BY r.created_at DESC",
        (pid,)
    ).fetchall()
    avg_rating = con.execute("SELECT AVG(rating) FROM reviews WHERE product_id=?", (pid,)).fetchone()[0]
    related = con.execute(
        "SELECT * FROM products WHERE category=? AND id!=? AND is_active=1 ORDER BY RANDOM() LIMIT 3",
        (p["category"], pid)
    ).fetchall()
    con.close()
    in_wishlist = False
    if session.get("user_id"):
        con2 = get_db()
        wl = con2.execute("SELECT id FROM wishlist WHERE user_id=? AND product_id=?",
                          (session["user_id"], pid)).fetchone()
        in_wishlist = bool(wl)
        con2.close()
    return render_template("product.html", p=p, reviews=reviews,
                           avg_rating=avg_rating, related=related, in_wishlist=in_wishlist)

@app.route("/cart")
def cart():
    return render_template("cart.html")

@app.route("/track", methods=["GET", "POST"])
def track():
    order = None
    if request.method == "POST":
        oid = request.form.get("order_id", "").strip()
        con = get_db()
        order = con.execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone()
        con.close()
    elif session.get("user_id") and request.args.get("id"):
        con = get_db()
        order = con.execute("SELECT * FROM orders WHERE id=? AND user_id=?",
                            (request.args["id"], session["user_id"])).fetchone()
        con.close()
    return render_template("track.html", order=order)

# ─── AUTH ──────────────────────────────────────────────────────────────────
@app.route("/auth", methods=["GET", "POST"])
def auth():
    if session.get("user_id"):
        return redirect(url_for("profile"))
    if session.get("is_admin"):
        return redirect(url_for("admin_dashboard"))
    return render_template("auth.html")

@app.route("/register", methods=["POST"])
def register():
    name  = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    phone = request.form.get("phone", "").strip()
    pwd   = request.form.get("password", "")
    cpwd  = request.form.get("confirm_password", "")

    if not all([name, email, pwd]):
        flash("Please fill all required fields.", "error")
        return redirect(url_for("auth") + "#register")
    if pwd != cpwd:
        flash("Passwords do not match.", "error")
        return redirect(url_for("auth") + "#register")
    if len(pwd) < 6:
        flash("Password must be at least 6 characters.", "error")
        return redirect(url_for("auth") + "#register")

    con = get_db()
    existing = con.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
    if existing:
        flash("Email already registered. Please log in.", "error")
        con.close()
        return redirect(url_for("auth") + "#login")

    con.execute(
        "INSERT INTO users(name,email,phone,password) VALUES(?,?,?,?)",
        (name, email, phone, hash_password(pwd))
    )
    con.commit()
    user = con.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    con.close()

    session["user_id"] = user["id"]
    session["user_name"] = user["name"]
    session["user_email"] = user["email"]
    flash(f"Welcome, {name}! Your account has been created.", "success")
    return redirect(url_for("home"))

@app.route("/login", methods=["POST"])
def login():
    identifier = request.form.get("identifier", "").strip()
    pwd = request.form.get("password", "")
    admin_mode = request.form.get("admin_mode", "")

    # Admin login
    if admin_mode:
        if identifier in ADMINS and ADMINS[identifier] == pwd:
            session["is_admin"] = True
            session["admin_name"] = identifier
            flash(f"Welcome back, {identifier}!", "success")
            return redirect(url_for("admin_dashboard"))
        flash("Invalid admin credentials.", "error")
        return redirect(url_for("auth") + "#admin")

    # User login
    con = get_db()
    user = con.execute(
        "SELECT * FROM users WHERE (email=? OR phone=?) AND is_active=1",
        (identifier.lower(), identifier)
    ).fetchone()
    con.close()

    if not user or user["password"] != hash_password(pwd):
        flash("Invalid email/phone or password.", "error")
        return redirect(url_for("auth") + "#login")

    session["user_id"] = user["id"]
    session["user_name"] = user["name"]
    session["user_email"] = user["email"]
    next_url = request.form.get("next") or url_for("home")
    flash(f"Welcome back, {user['name']}!", "success")
    return redirect(next_url)

@app.route("/logout")
def logout():
    session.clear()
    flash("You've been logged out.", "info")
    return redirect(url_for("home"))

@app.route("/forgot-password", methods=["POST"])
def forgot_password():
    email = request.form.get("email", "").strip().lower()
    con = get_db()
    user = con.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()

    if user:
        token  = secrets.token_urlsafe(32)
        expiry = (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        con.execute("UPDATE users SET reset_token=?, reset_expiry=? WHERE email=?",
                    (token, expiry, email))
        con.commit()
        reset_url = url_for("reset_password", token=token, _external=True)

        sent = send_reset_email(email, reset_url)
        if sent:
            flash("Password reset email sent! Check your inbox (and spam folder).", "success")
        else:
            flash(f"Could not send email. Use this link: {reset_url}", "warning")
    else:
        # Same message whether email exists or not (security best practice)
        flash("If that email is registered, a reset link has been sent.", "info")

    con.close()
    return redirect(url_for("auth") + "#forgot")

@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    con = get_db()
    user = con.execute(
        "SELECT * FROM users WHERE reset_token=?", (token,)
    ).fetchone()
    if not user or datetime.strptime(user["reset_expiry"], "%Y-%m-%d %H:%M:%S") < datetime.now():
        flash("Reset link is invalid or expired.", "error")
        con.close()
        return redirect(url_for("auth"))
    if request.method == "POST":
        pwd = request.form.get("password", "")
        if len(pwd) < 6:
            flash("Password must be at least 6 characters.", "error")
            return render_template("reset_password.html", token=token)
        con.execute("UPDATE users SET password=?, reset_token=NULL, reset_expiry=NULL WHERE id=?",
                    (hash_password(pwd), user["id"]))
        con.commit()
        con.close()
        flash("Password reset successfully. Please log in.", "success")
        return redirect(url_for("auth"))
    con.close()
    return render_template("reset_password.html", token=token)

# ─── ORDER ─────────────────────────────────────────────────────────────────
@app.route("/order", methods=["POST"])
def order():
    pid = request.form.get("product_id", "")
    con = get_db()
    p = con.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
    if not p:
        abort(404)

    qty = int(request.form.get("quantity", 1))
    total = p["price"] * qty
    now = datetime.now().strftime("%d %b %Y, %I:%M %p")

    cur = con.cursor()
    cur.execute(
        """INSERT INTO orders(created_at,user_id,customer_name,contact,email,address,
           product_id,product_name,quantity,unit_price,total_price,details,updated_at)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (now,
         session.get("user_id"),
         request.form.get("customer_name",""),
         request.form.get("contact",""),
         request.form.get("email",""),
         request.form.get("address",""),
         pid, p["name"], qty, p["price"], total,
         request.form.get("details",""),
         now)
    )
    con.execute("UPDATE products SET stock=MAX(0,stock-?) WHERE id=?", (qty, pid))
    con.commit()
    oid = cur.lastrowid
    con.close()

    return render_template("thankyou.html",
                           name=request.form.get("customer_name",""),
                           order_id=oid, total=total, product=p)

# ─── ORDER API (used by cart.html fetch — returns JSON instead of HTML) ────
@app.route("/order/api", methods=["POST"])
def order_api():
    pid = request.form.get("product_id", "")
    con = get_db()
    p = con.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
    if not p:
        return jsonify({"error": "product not found"}), 404

    qty = int(request.form.get("quantity", 1))
    total = p["price"] * qty
    now = datetime.now().strftime("%d %b %Y, %I:%M %p")

    cur = con.cursor()
    cur.execute(
        """INSERT INTO orders(created_at,user_id,customer_name,contact,email,address,
           product_id,product_name,quantity,unit_price,total_price,details,updated_at)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (now,
         session.get("user_id"),
         request.form.get("customer_name",""),
         request.form.get("contact",""),
         request.form.get("email",""),
         request.form.get("address",""),
         pid, p["name"], qty, p["price"], total,
         request.form.get("details",""),
         now)
    )
    con.execute("UPDATE products SET stock=MAX(0,stock-?) WHERE id=?", (qty, pid))
    con.commit()
    oid = cur.lastrowid
    con.close()
    return jsonify({"order_id": oid, "total": total, "product_name": p["name"]})

# ─── THANK YOU PAGE (GET — used after cart checkout) ───────────────────────
@app.route("/thankyou/<int:oid>")
def thankyou(oid):
    con = get_db()
    o = con.execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone()
    con.close()
    if not o:
        abort(404)
    # Build a minimal product-like object so thankyou.html works unchanged
    class _P:
        name = o["product_name"]
    return render_template("thankyou.html",
                           name=o["customer_name"],
                           order_id=o["id"],
                           total=o["total_price"],
                           product=_P())

# ─── USER PROFILE ──────────────────────────────────────────────────────────
@app.route("/profile")
@login_required
def profile():
    con = get_db()
    user = con.execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()
    orders = con.execute(
        "SELECT * FROM orders WHERE user_id=? ORDER BY id DESC",
        (session["user_id"],)
    ).fetchall()
    wishlist = con.execute(
        "SELECT p.* FROM products p JOIN wishlist w ON p.id=w.product_id WHERE w.user_id=?",
        (session["user_id"],)
    ).fetchall()
    con.close()
    return render_template("profile.html", user=user, orders=orders, wishlist=wishlist)

@app.route("/profile/update", methods=["POST"])
@login_required
def update_profile():
    name  = request.form.get("name","").strip()
    phone = request.form.get("phone","").strip()
    con = get_db()
    con.execute("UPDATE users SET name=?, phone=? WHERE id=?",
                (name, phone, session["user_id"]))
    con.commit()
    con.close()
    session["user_name"] = name
    flash("Profile updated successfully.", "success")
    return redirect(url_for("profile"))

@app.route("/wishlist/toggle/<pid>")
@login_required
def toggle_wishlist(pid):
    con = get_db()
    existing = con.execute("SELECT id FROM wishlist WHERE user_id=? AND product_id=?",
                           (session["user_id"], pid)).fetchone()
    if existing:
        con.execute("DELETE FROM wishlist WHERE user_id=? AND product_id=?",
                    (session["user_id"], pid))
        action = "removed"
    else:
        con.execute("INSERT INTO wishlist(user_id,product_id) VALUES(?,?)",
                    (session["user_id"], pid))
        action = "added"
    con.commit()
    con.close()
    return jsonify({"status": action})

@app.route("/review/<pid>", methods=["POST"])
@login_required
def add_review(pid):
    rating = int(request.form.get("rating", 5))
    comment = request.form.get("comment","").strip()
    con = get_db()
    existing = con.execute("SELECT id FROM reviews WHERE user_id=? AND product_id=?",
                           (session["user_id"], pid)).fetchone()
    if existing:
        con.execute("UPDATE reviews SET rating=?, comment=? WHERE user_id=? AND product_id=?",
                    (rating, comment, session["user_id"], pid))
    else:
        con.execute("INSERT INTO reviews(user_id,product_id,rating,comment) VALUES(?,?,?,?)",
                    (session["user_id"], pid, rating, comment))
    con.commit()
    con.close()
    flash("Review submitted!", "success")
    return redirect(url_for("product", pid=pid))

# ─── ADMIN ─────────────────────────────────────────────────────────────────
@app.route("/admin")
@admin_required
def admin_dashboard():
    con = get_db()
    total_orders   = con.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    new_orders     = con.execute("SELECT COUNT(*) FROM orders WHERE status='New'").fetchone()[0]
    total_users    = con.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    total_products = con.execute("SELECT COUNT(*) FROM products WHERE is_active=1").fetchone()[0]
    revenue        = con.execute("SELECT COALESCE(SUM(total_price),0) FROM orders WHERE status!='Cancelled'").fetchone()[0]
    recent_orders  = con.execute("SELECT * FROM orders ORDER BY id DESC LIMIT 10").fetchall()
    order_stats    = con.execute(
        "SELECT status, COUNT(*) as cnt FROM orders GROUP BY status"
    ).fetchall()
    low_stock = con.execute("SELECT * FROM products WHERE stock<=5 AND is_active=1").fetchall()
    con.close()
    return render_template("admin/dashboard.html",
        total_orders=total_orders, new_orders=new_orders,
        total_users=total_users, total_products=total_products,
        revenue=revenue, recent_orders=recent_orders,
        order_stats=order_stats, low_stock=low_stock,
        admin_name=session.get("admin_name","Admin"))

@app.route("/admin/orders")
@admin_required
def admin_orders():
    status = request.args.get("status","")
    search = request.args.get("q","")
    con = get_db()
    q = "SELECT * FROM orders WHERE 1=1"
    params = []
    if status:
        q += " AND status=?"
        params.append(status)
    if search:
        q += " AND (customer_name LIKE ? OR contact LIKE ? OR CAST(id AS TEXT) LIKE ?)"
        params += [f"%{search}%", f"%{search}%", f"%{search}%"]
    q += " ORDER BY id DESC"
    orders = con.execute(q, params).fetchall()
    con.close()
    return render_template("admin/orders.html", orders=orders,
                           selected_status=status, search=search)

@app.route("/admin/orders/update/<int:oid>", methods=["POST"])
@admin_required
def admin_update_order(oid):
    status = request.form.get("status","")
    note   = request.form.get("tracking_note","")
    now    = datetime.now().strftime("%d %b %Y, %I:%M %p")
    con = get_db()
    con.execute("UPDATE orders SET status=?, tracking_note=?, updated_at=? WHERE id=?",
                (status, note, now, oid))
    con.commit()
    con.close()
    flash("Order updated.", "success")
    return redirect(url_for("admin_orders"))

@app.route("/admin/orders/delete/<int:oid>", methods=["POST"])
@admin_required
def admin_delete_order(oid):
    con = get_db()
    con.execute("DELETE FROM orders WHERE id=?", (oid,))
    con.commit()
    con.close()
    flash("Order deleted.", "success")
    return redirect(url_for("admin_orders"))

@app.route("/admin/products")
@admin_required
def admin_products():
    con = get_db()
    products = con.execute("SELECT * FROM products ORDER BY created_at DESC").fetchall()
    con.close()
    return render_template("admin/products.html", products=products)

# ── ADD PRODUCT ─────────────────────────────────────────────────────────────
@app.route("/admin/products/add", methods=["POST"])
@admin_required
def admin_add_product():
    pid   = re.sub(r"[^a-z0-9-]","", request.form.get("id","").lower().strip())
    name  = request.form.get("name","").strip()
    price = int(request.form.get("price",0))
    stock = int(request.form.get("stock",0))
    desc  = request.form.get("description","").strip()
    crit  = request.form.get("criteria","").strip()
    best  = request.form.get("best_for","").strip()
    cat   = request.form.get("category","General").strip()

    image  = save_image("image")
    image2 = save_image("image2")

    if not pid or not name:
        flash("Product ID and name are required.", "error")
        return redirect(url_for("admin_products"))

    con = get_db()
    try:
        con.execute(
            "INSERT INTO products(id,name,image,image2,price,description,criteria,best_for,category,stock) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (pid, name, image, image2, price, desc, crit, best, cat, stock)
        )
        con.commit()
        flash(f"Product '{name}' added.", "success")
    except sqlite3.IntegrityError:
        flash("Product ID already exists.", "error")
    con.close()
    return redirect(url_for("admin_products"))

# ── EDIT PRODUCT ─────────────────────────────────────────────────────────────
@app.route("/admin/products/edit/<pid>", methods=["POST"])
@admin_required
def admin_edit_product(pid):
    con = get_db()
    current = con.execute("SELECT image, image2 FROM products WHERE id=?", (pid,)).fetchone()
    current_image  = current["image"]  if current else ""
    current_image2 = current["image2"] if current else ""

    new_image  = save_image("image")
    new_image2 = save_image("image2")
    image  = new_image  if new_image  else current_image
    image2 = new_image2 if new_image2 else current_image2

    con.execute(
        "UPDATE products SET name=?,price=?,stock=?,description=?,criteria=?,best_for=?,category=?,image=?,image2=?,is_active=? WHERE id=?",
        (
            request.form.get("name",""),
            int(request.form.get("price",0)),
            int(request.form.get("stock",0)),
            request.form.get("description",""),
            request.form.get("criteria",""),
            request.form.get("best_for",""),
            request.form.get("category","General"),
            image,
            image2,
            int(request.form.get("is_active",1)),
            pid
        )
    )
    con.commit()
    con.close()
    flash("Product updated.", "success")
    return redirect(url_for("admin_products"))

@app.route("/admin/products/delete/<pid>", methods=["POST"])
@admin_required
def admin_delete_product(pid):
    con = get_db()
    con.execute("UPDATE products SET is_active=0 WHERE id=?", (pid,))
    con.commit()
    con.close()
    flash("Product deactivated.", "success")
    return redirect(url_for("admin_products"))

@app.route("/admin/users")
@admin_required
def admin_users():
    search = request.args.get("q","")
    con = get_db()
    q = "SELECT u.*, COUNT(o.id) as order_count FROM users u LEFT JOIN orders o ON u.id=o.user_id"
    params = []
    if search:
        q += " WHERE u.name LIKE ? OR u.email LIKE ? OR u.phone LIKE ?"
        params = [f"%{search}%",f"%{search}%",f"%{search}%"]
    q += " GROUP BY u.id ORDER BY u.id DESC"
    users = con.execute(q, params).fetchall()
    con.close()
    return render_template("admin/users.html", users=users, search=search)

@app.route("/admin/users/toggle/<int:uid>", methods=["POST"])
@admin_required
def admin_toggle_user(uid):
    con = get_db()
    user = con.execute("SELECT is_active FROM users WHERE id=?", (uid,)).fetchone()
    con.execute("UPDATE users SET is_active=? WHERE id=?", (1-user["is_active"], uid))
    con.commit()
    con.close()
    flash("User status updated.", "success")
    return redirect(url_for("admin_users"))

@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    session.pop("admin_name", None)
    flash("Admin logged out.", "info")
    return redirect(url_for("auth"))

# ─── API (for cart JS) ──────────────────────────────────────────────────────
@app.route("/api/product/<pid>")
def api_product(pid):
    con = get_db()
    p = con.execute("SELECT id,name,price,image,image2,stock FROM products WHERE id=? AND is_active=1", (pid,)).fetchone()
    con.close()
    if not p:
        return jsonify({"error": "not found"}), 404
    return jsonify(dict(p))

@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404

if __name__ == "__main__":
    init_db()
    app.run(debug=True)