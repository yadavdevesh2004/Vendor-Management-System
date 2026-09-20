import os
import re
import sqlite3
import io
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, 
            template_folder=os.path.join(BASE_DIR, 'templates'),
            static_folder=os.path.join(BASE_DIR, 'static'))

app.secret_key = "vms_secret_key_pro_2026"
DB_NAME = "vms.db"

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            email TEXT UNIQUE,
            password TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vendors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT NOT NULL,
            category TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            base_price REAL NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS quotations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vendor_id INTEGER,
            product_id INTEGER,
            quoted_price REAL NOT NULL,
            delivery_days INTEGER NOT NULL,
            FOREIGN KEY(vendor_id) REFERENCES vendors(id) ON DELETE CASCADE,
            FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS purchase_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            po_number TEXT UNIQUE,
            vendor_id INTEGER,
            product_id INTEGER,
            quantity INTEGER,
            unit_price REAL,
            total_amount REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(vendor_id) REFERENCES vendors(id) ON DELETE CASCADE,
            FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE
        )
    ''')

    cursor.execute("SELECT * FROM users WHERE username = 'admin'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
                       ('admin', 'admin@vms.com', 'Admin@12345#'))

    conn.commit()
    conn.close()

def is_valid_password(password):
    if len(password) < 8:
        return False
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False
    return True

@app.before_request
def check_auth():
    open_endpoints = ['login', 'static']
    if 'user' not in session and request.endpoint not in open_endpoints:
        return redirect(url_for('login'))

@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        login_input = request.form.get('login_input', '').strip()
        password = request.form.get('password', '').strip()

        if not is_valid_password(password):
            flash('Password must be at least 8 characters long and contain at least 1 special character.', 'danger')
            return render_template('login.html')

        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE (username = ? OR email = ?) AND password = ?",
            (login_input, login_input, password)
        ).fetchone()
        conn.close()

        if user:
            session['user'] = user['username']
            flash('Login Successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid Credentials.', 'danger')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    conn = get_db_connection()
    vendor_count = conn.execute("SELECT COUNT(*) FROM vendors").fetchone()[0]
    product_count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    quote_count = conn.execute("SELECT COUNT(*) FROM quotations").fetchone()[0]
    po_count = conn.execute("SELECT COUNT(*) FROM purchase_orders").fetchone()[0]
    conn.close()
    return render_template('dashboard.html', 
                           vendor_count=vendor_count, 
                           product_count=product_count, 
                           quote_count=quote_count, 
                           po_count=po_count)

@app.route('/add-vendor', methods=['GET', 'POST'])
def add_vendor():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        category = request.form.get('category')

        conn = get_db_connection()
        conn.execute("INSERT INTO vendors (name, email, phone, category) VALUES (?, ?, ?, ?)",
                     (name, email, phone, category))
        conn.commit()
        conn.close()
        flash('Vendor added successfully!', 'success')
        return redirect(url_for('add_vendor'))

    conn = get_db_connection()
    vendors = conn.execute("SELECT * FROM vendors").fetchall()
    conn.close()
    return render_template('add_vendor.html', vendors=vendors)

@app.route('/delete-vendor/<int:id>')
def delete_vendor(id):
    conn = get_db_connection()
    conn.execute("DELETE FROM vendors WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    flash('Vendor deleted successfully!', 'warning')
    return redirect(url_for('add_vendor'))

@app.route('/add-product', methods=['GET', 'POST'])
def add_product():
    if request.method == 'POST':
        name = request.form.get('name')
        category = request.form.get('category')
        base_price = request.form.get('base_price')

        conn = get_db_connection()
        conn.execute("INSERT INTO products (name, category, base_price) VALUES (?, ?, ?)",
                     (name, category, float(base_price)))
        conn.commit()
        conn.close()
        flash('Product added successfully!', 'success')
        return redirect(url_for('add_product'))

    conn = get_db_connection()
    products = conn.execute("SELECT * FROM products").fetchall()
    conn.close()
    return render_template('add_product.html', products=products)

@app.route('/delete-product/<int:id>')
def delete_product(id):
    conn = get_db_connection()
    conn.execute("DELETE FROM products WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    flash('Product deleted successfully!', 'warning')
    return redirect(url_for('add_product'))

@app.route('/upload-quotation', methods=['GET', 'POST'])
def upload_quotation():
    conn = get_db_connection()
    if request.method == 'POST':
        vendor_id = request.form.get('vendor_id')
        product_id = request.form.get('product_id')
        quoted_price = request.form.get('quoted_price')
        delivery_days = request.form.get('delivery_days')

        conn.execute("INSERT INTO quotations (vendor_id, product_id, quoted_price, delivery_days) VALUES (?, ?, ?, ?)",
                     (vendor_id, product_id, float(quoted_price), int(delivery_days)))
        conn.commit()
        flash('Quotation saved successfully!', 'success')

    vendors = conn.execute("SELECT * FROM vendors").fetchall()
    products = conn.execute("SELECT * FROM products").fetchall()
    conn.close()
    return render_template('upload_quotation.html', vendors=vendors, products=products)

@app.route('/compare-quotations')
def compare_quotations():
    product_id = request.args.get('product_id')
    conn = get_db_connection()
    products = conn.execute("SELECT * FROM products").fetchall()

    quotations = []
    if product_id:
        quotations = conn.execute('''
            SELECT q.id, v.name as vendor_name, p.name as product_name, q.quoted_price, q.delivery_days
            FROM quotations q
            JOIN vendors v ON q.vendor_id = v.id
            JOIN products p ON q.product_id = p.id
            WHERE q.product_id = ?
            ORDER BY q.quoted_price ASC
        ''', (product_id,)).fetchall()

    conn.close()
    return render_template('compare_quotations.html', products=products, quotations=quotations, selected_product=product_id)

@app.route('/generate-po', methods=['GET', 'POST'])
def generate_po():
    conn = get_db_connection()
    if request.method == 'POST':
        vendor_id = request.form.get('vendor_id')
        product_id = request.form.get('product_id')
        quantity = int(request.form.get('quantity'))
        unit_price = float(request.form.get('unit_price'))
        total_amount = quantity * unit_price
        
        count = conn.execute("SELECT COUNT(*) FROM purchase_orders").fetchone()[0]
        po_number = f"PO-{1001 + count}"

        conn.execute('''
            INSERT INTO purchase_orders (po_number, vendor_id, product_id, quantity, unit_price, total_amount)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (po_number, vendor_id, product_id, quantity, unit_price, total_amount))
        conn.commit()
        flash(f'Purchase Order {po_number} generated successfully!', 'success')
        return redirect(url_for('generate_po'))

    vendors = conn.execute("SELECT * FROM vendors").fetchall()
    products = conn.execute("SELECT * FROM products").fetchall()
    pos = conn.execute('''
        SELECT po.*, v.name as vendor_name, p.name as product_name
        FROM purchase_orders po
        JOIN vendors v ON po.vendor_id = v.id
        JOIN products p ON po.product_id = p.id
        ORDER BY po.id DESC
    ''').fetchall()
    conn.close()
    return render_template('generate_po.html', vendors=vendors, products=products, pos=pos)

@app.route('/view-reports')
def view_reports():
    conn = get_db_connection()
    reports = conn.execute('''
        SELECT po.po_number, v.name as vendor_name, p.name as product_name, 
               po.quantity, po.unit_price, po.total_amount, po.created_at
        FROM purchase_orders po
        JOIN vendors v ON po.vendor_id = v.id
        JOIN products p ON po.product_id = p.id
        ORDER BY po.id DESC
    ''').fetchall()
    conn.close()
    return render_template('view_reports.html', reports=reports)

@app.route('/download-report')
def download_report():
    conn = get_db_connection()
    reports = conn.execute('''
        SELECT po.po_number, v.name as vendor_name, p.name as product_name, 
               po.quantity, po.total_amount, po.created_at
        FROM purchase_orders po
        JOIN vendors v ON po.vendor_id = v.id
        JOIN products p ON po.product_id = p.id
        ORDER BY po.id DESC
    ''').fetchall()
    conn.close()

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    pdf.setTitle("Vendor_Purchase_Report")

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(50, 750, "Vendor Management System - Purchase Report")
    pdf.setFont("Helvetica", 10)
    pdf.drawString(50, 735, "Generated Summary of all completed Purchase Orders")
    pdf.line(50, 725, 550, 725)

    y = 700
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(50, y, "PO Number")
    pdf.drawString(140, y, "Vendor")
    pdf.drawString(260, y, "Product")
    pdf.drawString(410, y, "Qty")
    pdf.drawString(460, y, "Total (INR)")

    y -= 15
    pdf.setFont("Helvetica", 9)
    for r in reports:
        if y < 50:
            pdf.showPage()
            y = 750
        pdf.drawString(50, y, str(r['po_number']))
        pdf.drawString(140, y, str(r['vendor_name'])[:18])
        pdf.drawString(260, y, str(r['product_name'])[:22])
        pdf.drawString(410, y, str(r['quantity']))
        pdf.drawString(460, y, f"INR {r['total_amount']:.2f}")
        y -= 20

    pdf.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="Purchase_Orders_Report.pdf", mimetype='application/pdf')

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
else:
 
    init_db()