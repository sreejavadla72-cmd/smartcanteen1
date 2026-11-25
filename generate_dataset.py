
import csv
import random
from datetime import date, timedelta
from pathlib import Path

# Reproducible sample data
random.seed(42)

OUTPUT_FOLDER = Path("data")
OUTPUT_FOLDER.mkdir(exist_ok=True)

OUTPUT_FILE = OUTPUT_FOLDER / "historical_food_sales.csv"

food_items = {
    "Samosa": 45,
    "Egg Puff": 35,
    "Veg Sandwich": 25,
    "Idli": 50,
    "Dosa": 40,
    "Tea": 70,
    "Veg Meals": 30,
    "Lemon Juice": 25
}

# Example calendar markers for this project.
# Add or correct dates according to your canteen calendar.
festival_dates = {
    (1, 14): "Sankranti",
    (8, 15): "Independence Day",
    (10, 2): "Gandhi Jayanti",
    (12, 25): "Christmas"
}

holiday_dates = {
    (1, 14),
    (8, 15),
    (10, 2),
    (12, 25),
    (1, 26)
}

start_date = date(2025, 1, 1)
end_date = date(2026, 10, 31)

rows = []
current_date = start_date

while current_date <= end_date:
    day_name = current_date.strftime("%A")
    month_name = current_date.strftime("%B")
    month = current_date.month
    year = current_date.year
    weekday = current_date.weekday()

    is_weekend = 1 if weekday >= 5 else 0
    is_holiday = 1 if (month, current_date.day) in holiday_dates else 0
    festival = festival_dates.get(
        (month, current_date.day), "None"
    )

    for food_name, base_quantity in food_items.items():

        # Small demand variations by day and season
        quantity = base_quantity

        if is_weekend:
            quantity *= 1.15

        if is_holiday:
            quantity *= 1.20

        if festival != "None":
            quantity *= 1.35

        # Different food demand in different months
        if food_name == "Lemon Juice" and month in [3, 4, 5, 6]:
            quantity *= 1.25

        if food_name in ["Idli", "Dosa"] and weekday < 5:
            quantity *= 1.10

        # Random variation to make the sample data realistic
        quantity += random.randint(-5, 5)

        quantity = max(0, round(quantity))

        rows.append({
            "Date": current_date.isoformat(),
            "Day": day_name,
            "Month": month_name,
            "Month_Number": month,
            "Year": year,
            "Weekday_Number": weekday,
            "Is_Weekend": is_weekend,
            "Is_Holiday": is_holiday,
            "Festival": festival,
            "Food_Item": food_name,
            "Quantity_Sold": quantity
        })

    current_date += timedelta(days=1)

fieldnames = [
    "Date",
    "Day",
    "Month",
    "Month_Number",
    "Year",
    "Weekday_Number",
    "Is_Weekend",
    "Is_Holiday",
    "Festival",
    "Food_Item",
    "Quantity_Sold"
]

with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as file:
    writer = csv.DictWriter(file, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print("Historical dataset created successfully!")
print("File:", OUTPUT_FILE)
print("Total records:", len(rows))
print("Food items:", len(food_items))
print("Start date:", start_date)
print("End date:", end_date)
