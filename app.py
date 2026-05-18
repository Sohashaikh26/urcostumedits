
from flask import Flask, render_template, request, redirect, url_for
import sqlite3, os
from datetime import datetime

app = Flask(__name__)
DB = "orders.db"
ADMIN_PIN = os.environ.get("ADMIN_PIN", "1234")

PRODUCTS = [
 {"id":"heart","name":"Heart Crochet Keychain","image":"heart.jpeg","price":"Starting ₹99","description":"A cute handmade crochet heart keychain with soft yarn texture and a warm aesthetic finish.","criteria":["Choose any heart colour","Initial/name can be added","Keyring included","Gift packing available"],"best_for":"Couples, best friends, birthdays, hampers"},
 {"id":"bow","name":"Bow Crochet Keychain","image":"bow.jpeg","price":"Starting ₹99","description":"A soft pink bow crochet keychain with a coquette, cute and premium handmade look.","criteria":["Colour can be customised","Small/medium size available","Keyring included","Bulk orders available"],"best_for":"Pouches, bags, birthday hampers, girly gifts"},
 {"id":"evil-eye","name":"Evil Eye Heart Keychain","image":"evil-eye.jpeg","price":"Starting ₹120","description":"A blue evil-eye inspired heart crochet keychain with bold handmade detailing.","criteria":["Evil eye or plain heart style","Colour shades can be changed","Keyring included","Gift packing available"],"best_for":"Bag charms, bestie gifts, protection-themed gifts"},
 {"id":"letter","name":"Alphabet Crochet Keychain","image":"letter.jpeg","price":"Starting ₹120","description":"A personalised crochet alphabet keychain made in your selected letter and colour combination.","criteria":["Any alphabet A-Z","Two-colour combination","Name tag can be added","Bulk orders accepted"],"best_for":"School bags, farewell gifts, class orders, personal gifts"},
 {"id":"cross","name":"Cross Crochet Keychain","image":"cross.jpeg","price":"Starting ₹99","description":"A simple and elegant handmade crochet cross keychain in warm cream and brown tones.","criteria":["Colour combination can be selected","Small/medium size","Keyring included","Gift packing available"],"best_for":"Faith gifts, Christmas gifts, personal keychains"}
]

def init_db():
    con=sqlite3.connect(DB)
    con.execute("""CREATE TABLE IF NOT EXISTS orders(
        id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, customer_name TEXT,
        contact TEXT, product TEXT, quantity INTEGER, details TEXT, status TEXT DEFAULT 'New')""")
    con.commit(); con.close()

def find_product(pid):
    return next((p for p in PRODUCTS if p["id"]==pid), None)

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/products")
def products():
    return render_template("products.html", products=PRODUCTS)

@app.route("/product/<pid>")
def product(pid):
    p=find_product(pid)
    if not p: return "Product not found",404
    return render_template("product.html", p=p)

@app.route("/order", methods=["POST"])
def order():
    con=sqlite3.connect(DB)
    con.execute("INSERT INTO orders(created_at,customer_name,contact,product,quantity,details) VALUES(?,?,?,?,?,?)",
        (datetime.now().strftime("%d %b %Y, %I:%M %p"), request.form["customer_name"], request.form["contact"],
         request.form["product"], int(request.form["quantity"]), request.form["details"]))
    con.commit(); con.close()
    return render_template("thankyou.html", name=request.form["customer_name"])

@app.route("/admin")
def admin():
    pin=request.args.get("pin","")
    if pin != ADMIN_PIN:
        return render_template("admin_login.html")
    con=sqlite3.connect(DB); con.row_factory=sqlite3.Row
    orders=con.execute("SELECT * FROM orders ORDER BY id DESC").fetchall()
    con.close()
    return render_template("admin.html", orders=orders, pin=pin,
        total=len(orders),
        new=sum(1 for o in orders if o["status"]=="New"),
        making=sum(1 for o in orders if o["status"]=="Making"),
        ready=sum(1 for o in orders if o["status"]=="Ready"))

@app.route("/admin/update/<int:oid>", methods=["POST"])
def update_order(oid):
    pin=request.args.get("pin","")
    con=sqlite3.connect(DB)
    con.execute("UPDATE orders SET status=? WHERE id=?", (request.form["status"], oid))
    con.commit(); con.close()
    return redirect(url_for("admin", pin=pin))

if __name__=="__main__":
    init_db()
    app.run(debug=True)
