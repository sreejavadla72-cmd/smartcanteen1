
from flask import (
    Flask, render_template, request,
    redirect, url_for, session, flash
)
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db_connection
from functools import wraps
from datetime import date, timedelta
from pathlib import Path
import pandas as pd
import os

app = Flask(__name__)

# Secret key for session security
app.secret_key = os.environ.get(
    "SECRET_KEY",
    "smart-canteen-development-key-change-before-deployment"
)


# -----------------------------------------
# DATABASE HELPER
# -----------------------------------------

def query_db(sql, values=(), fetch=True):
    connection = get_db_connection()

    if connection is None:
        raise RuntimeError("Database connection failed.")

    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute(sql, values)

        if fetch:
            result = cursor.fetchall()
            return result

        connection.commit()
        return cursor.lastrowid

    finally:
        cursor.close()
        connection.close()


# -----------------------------------------
# MACHINE LEARNING CSV HELPER
# -----------------------------------------

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"


def read_ml_csv(filename):
    file_path = DATA_DIR / filename

    if not file_path.exists():
        return []

    try:
        dataframe = pd.read_csv(file_path)
        dataframe = dataframe.fillna("")
        return dataframe.to_dict(orient="records")

    except Exception as error:
        print("ML CSV reading error:", error)
        return []


# -----------------------------------------
# LOGIN REQUIRED DECORATOR
# -----------------------------------------

def login_required(route_function):
    @wraps(route_function)
    def wrapper(*args, **kwargs):
        if "admin_id" not in session:
            return redirect(url_for("login"))

        return route_function(*args, **kwargs)

    return wrapper


# -----------------------------------------
# CREATE DEFAULT ADMIN
# -----------------------------------------

def create_default_admin():
    admins = query_db(
        "SELECT id FROM admins WHERE username = %s",
        ("admin",)
    )

    if not admins:
        query_db(
            """
            INSERT INTO admins (username, password_hash)
            VALUES (%s, %s)
            """,
            (
                "admin",
                generate_password_hash("Admin@123")
            ),
            fetch=False
        )


# -----------------------------------------
# LOGIN PAGE
# -----------------------------------------

@app.route("/", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])
def login():

    if "admin_id" in session:
        return redirect(url_for("index"))

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        admins = query_db(
            "SELECT * FROM admins WHERE username = %s",
            (username,)
        )

        if admins and check_password_hash(
            admins[0]["password_hash"], password
        ):
            session["admin_id"] = admins[0]["id"]
            session["username"] = username

            flash("Login successful!", "success")
            return redirect(url_for("index"))

        flash("Invalid username or password.", "danger")

    return render_template("login.html")


# -----------------------------------------
# LOGOUT
# -----------------------------------------

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# -----------------------------------------
# HOME PAGE
# -----------------------------------------

@app.route("/home")
@login_required
def index():

    food_count = query_db(
        "SELECT COUNT(*) AS total FROM food_items"
    )[0]["total"]

    sales_count = query_db(
        "SELECT COUNT(*) AS total FROM sales"
    )[0]["total"]

    today_sales = query_db(
        """
        SELECT COALESCE(SUM(total_amount), 0) AS total
        FROM sales
        WHERE DATE(sale_date) = CURDATE()
        """
    )[0]["total"]

    return render_template(
        "index.html",
        food_count=food_count,
        sales_count=sales_count,
        today_sales=today_sales
    )


# -----------------------------------------
# VIEW FOOD ITEMS
# -----------------------------------------

@app.route("/food")
@login_required
def food():

    items = query_db(
        "SELECT * FROM food_items ORDER BY id DESC"
    )

    return render_template("food.html", items=items)


# -----------------------------------------
# ADD FOOD ITEMS
# -----------------------------------------

@app.route("/add-food", methods=["GET", "POST"])
@login_required
def add_food():

    if request.method == "POST":

        food_name = request.form.get("food_name", "").strip()
        category = request.form.get("category", "").strip()
        price = request.form.get("price", "")
        quantity = request.form.get("quantity", "")
        description = request.form.get("description", "").strip()

        try:
            price = float(price)
            quantity = int(quantity)

            if not food_name or not category:
                raise ValueError()

            if price <= 0 or quantity < 0:
                raise ValueError()

            query_db(
                """
                INSERT INTO food_items
                (food_name, category, price,
                 quantity_available, description)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    food_name, category, price,
                    quantity, description
                ),
                fetch=False
            )

            flash("Food item added successfully!", "success")
            return redirect(url_for("food"))

        except ValueError:
            flash("Enter valid food details.", "danger")

    return render_template("add_food.html")


# -----------------------------------------
# SALES PAGE
# -----------------------------------------

@app.route("/sales", methods=["GET", "POST"])
@login_required
def sales():

    if request.method == "POST":

        food_id = request.form.get("food_id", "")
        quantity = request.form.get("quantity", "")

        try:
            food_id = int(food_id)
            quantity = int(quantity)

            if quantity <= 0:
                raise ValueError()

            connection = get_db_connection()

            if connection is None:
                raise RuntimeError("Database connection failed.")

            cursor = connection.cursor(dictionary=True)

            try:
                connection.start_transaction()

                cursor.execute(
                    """
                    SELECT id, price, quantity_available
                    FROM food_items
                    WHERE id = %s
                    FOR UPDATE
                    """,
                    (food_id,)
                )

                item = cursor.fetchone()

                if not item:
                    raise ValueError("Food item not found.")

                if item["quantity_available"] < quantity:
                    raise ValueError("Insufficient stock.")

                unit_price = item["price"]
                subtotal = unit_price * quantity

                cursor.execute(
                    "INSERT INTO sales (total_amount) VALUES (%s)",
                    (subtotal,)
                )

                sale_id = cursor.lastrowid

                cursor.execute(
                    """
                    INSERT INTO sale_items
                    (sale_id, food_id, quantity, unit_price, subtotal)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (sale_id, food_id, quantity, unit_price, subtotal)
                )

                cursor.execute(
                    """
                    UPDATE food_items
                    SET quantity_available = quantity_available - %s
                    WHERE id = %s
                    """,
                    (quantity, food_id)
                )

                connection.commit()

                flash("Sale recorded successfully!", "success")
                return redirect(url_for("sales_history"))

            except Exception:
                connection.rollback()
                raise

            finally:
                cursor.close()
                connection.close()

        except (ValueError, TypeError) as error:
            flash(str(error) or "Enter valid sale details.", "danger")

    items = query_db(
        """
        SELECT * FROM food_items
        WHERE quantity_available > 0
        ORDER BY food_name
        """
    )

    return render_template("sales.html", items=items)


# -----------------------------------------
# SALES DETAILS
# -----------------------------------------

@app.route("/sales-details")
@login_required
def sales_details():

    details = query_db(
        """
        SELECT
            si.id,
            s.id AS sale_id,
            s.sale_date,
            f.food_name,
            si.quantity,
            si.unit_price,
            si.subtotal
        FROM sale_items si
        JOIN sales s ON si.sale_id = s.id
        JOIN food_items f ON si.food_id = f.id
        ORDER BY s.sale_date DESC
        """
    )

    return render_template("sales_details.html", details=details)


# -----------------------------------------
# SALES HISTORY
# -----------------------------------------

@app.route("/sales-history")
@login_required
def sales_history():

    records = query_db(
        "SELECT * FROM sales ORDER BY sale_date DESC"
    )

    return render_template(
        "sales_history.html",
        records=records
    )


# -----------------------------------------
# DAILY SALES
# -----------------------------------------

@app.route("/daily-sales")
@login_required
def daily_sales():

    records = query_db(
        """
        SELECT DATE(sale_date) AS period,
               COUNT(*) AS total_orders,
               SUM(total_amount) AS total_sales
        FROM sales
        GROUP BY DATE(sale_date)
        ORDER BY period DESC
        """
    )

    return render_template(
        "daily_sales.html",
        records=records
    )


# -----------------------------------------
# WEEKLY SALES
# -----------------------------------------

@app.route("/weekly-sales")
@login_required
def weekly_sales():

    records = query_db(
        """
        SELECT YEAR(sale_date) AS sales_year,
               WEEK(sale_date, 3) AS week_number,
               COUNT(*) AS total_orders,
               SUM(total_amount) AS total_sales
        FROM sales
        GROUP BY YEAR(sale_date), WEEK(sale_date, 3)
        ORDER BY sales_year DESC, week_number DESC
        """
    )

    return render_template(
        "weekly_sales.html",
        records=records
    )


# -----------------------------------------
# MONTHLY SALES
# -----------------------------------------

@app.route("/monthly-sales")
@login_required
def monthly_sales():

    records = query_db(
        """
        SELECT YEAR(sale_date) AS sales_year,
               MONTH(sale_date) AS month_number,
               MONTHNAME(sale_date) AS month_name,
               COUNT(*) AS total_orders,
               SUM(total_amount) AS total_sales
        FROM sales
        GROUP BY YEAR(sale_date), MONTH(sale_date),
                 MONTHNAME(sale_date)
        ORDER BY sales_year DESC, month_number DESC
        """
    )

    return render_template(
        "monthly_sales.html",
        records=records
    )


# -----------------------------------------
# ADMIN DASHBOARD
# -----------------------------------------

@app.route("/dashboard")
@login_required
def dashboard():

    total_food = query_db(
        "SELECT COUNT(*) AS total FROM food_items"
    )[0]["total"]

    total_sales = query_db(
        "SELECT COALESCE(SUM(total_amount), 0) AS total FROM sales"
    )[0]["total"]

    total_orders = query_db(
        "SELECT COUNT(*) AS total FROM sales"
    )[0]["total"]

    low_stock = query_db(
        """
        SELECT * FROM food_items
        WHERE quantity_available <= 10
        ORDER BY quantity_available ASC
        """
    )

    chart_data = query_db(
        """
        SELECT DATE(sale_date) AS sale_day,
               SUM(total_amount) AS amount
        FROM sales
        WHERE sale_date >= CURDATE() - INTERVAL 6 DAY
        GROUP BY DATE(sale_date)
        ORDER BY sale_day
        """
    )

    # MACHINE LEARNING DASHBOARD DATA

    model_results = read_ml_csv("model_evaluation.csv")

    prediction_summary = read_ml_csv(
        "november_2026_summary.csv"
    )

    best_model = "Not Available"

    if model_results:
        best_result = min(
            model_results,
            key=lambda item: float(item.get("MAE", 999999))
        )

        best_model = best_result.get(
            "Model", "Not Available"
        )

    return render_template(
        "dashboard.html",
        total_food=total_food,
        total_sales=total_sales,
        total_orders=total_orders,
        low_stock=low_stock,
        chart_data=chart_data,
        model_results=model_results,
        prediction_summary=prediction_summary,
        best_model=best_model
    )


# -----------------------------------------
# FOOD DEMAND PREDICTIONS
# -----------------------------------------


@app.route("/predictions")
@login_required
def predictions():

    # Read machine learning CSV files

    daily_predictions = read_ml_csv(
        "november_2026_predictions.csv"
    )

    monthly_summary = read_ml_csv(
        "november_2026_summary.csv"
    )

    model_results = read_ml_csv(
        "model_evaluation.csv"
    )

    # Find the best model using the lowest MAE

    best_model = "Not Available"

    if model_results:
        best_result = min(
            model_results,
            key=lambda item: float(
                item.get("MAE", 999999)
            )
        )

        best_model = best_result.get(
            "Model", "Not Available"
        )

    return render_template(
        "predictions.html",
        daily_predictions=daily_predictions,
        monthly_summary=monthly_summary,
        model_results=model_results,
        best_model=best_model
    )



# -----------------------------------------
# APPLICATION START
# -----------------------------------------

if __name__ == "__main__":

    try:
        create_default_admin()
        print("Default admin account is ready.")
        print("Smart Canteen application is starting...")

        app.run(
            host="127.0.0.1",
            port=5000,
            debug=True
        )

    except Exception as error:
        print("Application startup error:", error)
