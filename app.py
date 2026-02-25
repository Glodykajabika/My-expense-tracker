from flask import (
    Flask, 
    render_template, 
    request, 
    url_for, 
    make_response, 
    flash,
    redirect, 
    Response
    )

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func

from datetime import date, datetime


app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///expenses.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = "my-secret-key"

db = SQLAlchemy(app)

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(120), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    date = db.Column(db.Date, nullable=False, default=date.today)
    

with app.app_context():
    db.create_all()

CATEGORIES = ["Food", "Transport", "Rent", "Utilities", "Health", "Others"]
    
def format_number(value):
    """Format a number with a commas as thousands separators and floats to 2 decimals"""
    
    return f"{value:,.2f}"

app.jinja_env.filters["format_number"] = format_number


def expense_filter(query, expense_to_filter, op, applied_filter):
    """
    Filter expenses, either by start date, end date, or category.
    query = query,
    expense_to_filter = the list of expenses you want to perfom the filtering on
    op = comparison operators (>= or <= or ==) 
    applied_filter = the filter to apply (start_date or end_date or category)
    """
    
    if op == ">=":
        return query.filter(expense_to_filter >= applied_filter)
    
    elif op == "<=":
        return query.filter(expense_to_filter <= applied_filter)
    
    elif op == "==":
        return query.filter(expense_to_filter == applied_filter)
    
    
def parse_date_or_none(s: str):
    if not s:
        return None
    
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    
    except ValueError:
        return None

@app.route("/")
def index():
    
    # Reading parameters (Filtering by date)
    start_str = (request.args.get("start") or "").strip()
    end_str = (request.args.get("end") or "").strip()
    selected_category = (request.args.get("category") or "").strip()
    
    # Parsing (Filtering by date)
    start_date = parse_date_or_none(start_str)
    end_date = parse_date_or_none(end_str)
    
    if start_date and end_date and end_date < start_date:
        flash("End date cannot be before start date", "error")
        start_date = end_date = None
        start_str = end_str = ""
        
    q = Expense.query
    
    # category query for  pie chart
    category_query = db.session.query(Expense.category, func.sum(Expense.amount))
    
    # date query for  day chart
    day_query = db.session.query(Expense.date, func.sum(Expense.amount))
    
    if start_date:
        q = expense_filter(q, Expense.date, ">=", start_date)
        category_query = expense_filter(category_query, Expense.date, ">=", start_date)
        day_query = expense_filter(day_query, Expense.date, ">=", start_date)
        
    if end_date:
        q = expense_filter(q, Expense.date, "<=", end_date)
        # category_query = expense_filter(category_query, Expense.date, "<=", end_date)
        # day_query = expense_filter(day_query, Expense.date, "<=", end_date)
        
    if selected_category:
        q = expense_filter(q, Expense.category, "==", selected_category)
        # category_query = expense_filter(category_query, Expense.category, "==", selected_category)
        # day_query = expense_filter(day_query, Expense.category, "==", selected_category)
        
        
        
    expenses = Expense.query.order_by(Expense.date.desc(), Expense.id.desc()).all()
    
    # For pie chart
    category_rows = category_query.group_by(Expense.category).all() # type: ignore #! To ignore the warning from pylint
    category_labels = [c for c, _ in category_rows]
    category_amounts = [round(float(a or 0), 2) for _, a in category_rows]
    
    # For day chart
    day_rows = day_query.group_by(Expense.date).order_by(Expense.date).all() # type: ignore #! To ignore the warning from pylint
    day_labels = [d.isoformat() for d, _ in day_rows]
    day_amounts = [round(float(a or 0), 2) for _, a in day_rows]
    
    
    total = round(sum(e.amount for e in expenses), 2)
    
    filtered_expenses = ""
    total_filtered_expenses = 0     
    
    if start_date or end_date or selected_category:
        filtered_expenses = q.order_by(Expense.date.desc(), Expense.id.desc()).all() # type: ignore #! To ignore the warning from pylint
        total_filtered_expenses = round(sum(e.amount for e in filtered_expenses), 2)

        
    return render_template(
        "index.html", 
        
        categories=CATEGORIES,
        today=date.today().isoformat(),
        total_filtered_expenses=total_filtered_expenses,
        expenses=expenses,
        filtered_expenses=filtered_expenses,
        total=total,
        start_str=start_str,
        end_str=end_str,
        selected_category=selected_category,
        category_labels=category_labels,
        category_amounts=category_amounts, 
        day_labels=day_labels,
        day_amounts=day_amounts
    )

@app.route("/add", methods=['POST'])
def add():
    
    description = (request.form.get("description") or "").strip()
    amount_str = (request.form.get("amount") or "").strip()
    category = (request.form.get("category") or "").strip()
    date_str = (request.form.get("date") or "").strip()
    
    if not description or not amount_str or not category:
        flash("please fill description, amount, and category", "error")
        
        return redirect(url_for("index"))
        
    try:
        amount = float(amount_str)
        
        if amount <= 0:
            raise ValueError
        
    except ValueError:
        flash("The amount must be a positive number", "error")
        
        return redirect(url_for("index"))
    
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else date.today()
        
    except ValueError:
        d = date.today()
        
    e = Expense(description=description, amount=amount, category=category, date=d) # type: ignore #! To ignore the warning from pylint
    
    db.session.add(e)
    db.session.commit()
    flash("Expense added", "success")
    
    return redirect(url_for("index"))

@app.route("/delete/<int:expense_id>", methods=["POST"])
def delete(expense_id):
    e = Expense.query.get_or_404(expense_id)
    db.session.delete(e)
    db.session.commit()
    flash("Expense deleted", "success")
    
    return redirect(url_for("index"))

@app.route("/export.csv")
def export_csv():
    # Reading parameters (Filtering by date)
    start_str = (request.args.get("start") or "").strip()
    end_str = (request.args.get("end") or "").strip()
    selected_category = (request.args.get("category") or "").strip()
    
    # Parsing (Filtering by date)
    start_date = parse_date_or_none(start_str)
    end_date = parse_date_or_none(end_str)
    
    q = Expense.query
    
    if start_date:
        q = expense_filter(q, Expense.date, ">=", start_date)
        
    if end_date:
        q = expense_filter(q, Expense.date, "<=", end_date)
        
    if selected_category:
        q = expense_filter(q, Expense.category, "==", selected_category)
        
    expenses = q.order_by(Expense.date.desc(), Expense.id.desc()).all() # type: ignore
    
    lines = ["date, description, category, amount"]
    
    for e in expenses:
        lines.append(f"{e.date}, {e.description}, {e.category}, {format_number(e.amount)}")
        
    csv_data = "\n".join(lines)
    
    filename_start = start_str or "all"
    filename_end = end_str or "all"
    filename = f"expenses_{filename_start}_to_{filename_end}.csv"
    
    return Response(
        csv_data,
        headers={
            "Content-Type":"text/csv",
            "Content-Disposition":f"attachment; filename={filename}"
        }
    )
    
if __name__ == "__main__":
    app.run(debug=True)