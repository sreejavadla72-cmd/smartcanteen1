
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import date, timedelta

from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.ensemble import RandomForestRegressor
from sklearn.tree import DecisionTreeRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

# --------------------------------------------------
# 1. FILE LOCATIONS
# --------------------------------------------------

DATA_FILE = Path("data/historical_food_sales.csv")
OUTPUT_FOLDER = Path("data")
OUTPUT_FOLDER.mkdir(exist_ok=True)

# --------------------------------------------------
# 2. LOAD HISTORICAL DATA
# --------------------------------------------------

if not DATA_FILE.exists():
    raise FileNotFoundError(
        "Dataset not found. Run python generate_dataset.py first."
    )

df = pd.read_csv(DATA_FILE)

required_columns = [
    "Date", "Day", "Month_Number", "Year",
    "Weekday_Number", "Is_Weekend", "Is_Holiday",
    "Festival", "Food_Item", "Quantity_Sold"
]

missing_columns = [
    column for column in required_columns
    if column not in df.columns
]

if missing_columns:
    raise ValueError(
        f"Missing dataset columns: {missing_columns}"
    )

df["Date"] = pd.to_datetime(df["Date"])
df = df.sort_values("Date").reset_index(drop=True)

# --------------------------------------------------
# 3. SELECT INPUT FEATURES AND TARGET
# --------------------------------------------------

feature_columns = [
    "Day",
    "Month_Number",
    "Year",
    "Weekday_Number",
    "Is_Weekend",
    "Is_Holiday",
    "Festival",
    "Food_Item"
]

target_column = "Quantity_Sold"

X = df[feature_columns]
y = df[target_column]

categorical_features = ["Day", "Festival", "Food_Item"]

numerical_features = [
    "Month_Number",
    "Year",
    "Weekday_Number",
    "Is_Weekend",
    "Is_Holiday"
]

# --------------------------------------------------
# 4. SPLIT DATA BY DATE
# Use earlier dates for training and later dates
# for testing.
# --------------------------------------------------

split_date = pd.Timestamp("2026-08-01")

train_mask = df["Date"] < split_date
test_mask = df["Date"] >= split_date

X_train = X.loc[train_mask]
X_test = X.loc[test_mask]

y_train = y.loc[train_mask]
y_test = y.loc[test_mask]

if X_train.empty or X_test.empty:
    raise ValueError("Training or testing data is empty.")

print("\nHistorical dataset loaded successfully.")
print("Total records:", len(df))
print("Training records:", len(X_train))
print("Testing records:", len(X_test))

# --------------------------------------------------
# 5. PREPROCESSING
# --------------------------------------------------

preprocessor = ColumnTransformer(
    transformers=[
        (
            "categorical",
            OneHotEncoder(handle_unknown="ignore"),
            categorical_features
        ),
        (
            "numerical",
            SimpleImputer(strategy="median"),
            numerical_features
        )
    ]
)

# --------------------------------------------------
# 6. CREATE THREE MACHINE LEARNING MODELS
# --------------------------------------------------

models = {
    "Linear Regression": LinearRegression(),

    "Decision Tree": DecisionTreeRegressor(
        max_depth=12,
        random_state=42
    ),

    "Random Forest": RandomForestRegressor(
        n_estimators=100,
        max_depth=15,
        random_state=42,
        n_jobs=-1
    )
}

results = []
trained_models = {}

# --------------------------------------------------
# 7. TRAIN AND EVALUATE MODELS
# --------------------------------------------------

print("\n========== MODEL EVALUATION ==========")

for model_name, algorithm in models.items():

    pipeline = Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("model", algorithm)
        ]
    )

    pipeline.fit(X_train, y_train)

    predictions = pipeline.predict(X_test)
    predictions = np.maximum(0, predictions)

    mae = mean_absolute_error(y_test, predictions)
    rmse = np.sqrt(mean_squared_error(y_test, predictions))
    r2 = r2_score(y_test, predictions)

    results.append({
        "Model": model_name,
        "MAE": round(mae, 2),
        "RMSE": round(rmse, 2),
        "R2_Score": round(r2, 4)
    })

    trained_models[model_name] = pipeline

    print("\nModel:", model_name)
    print("MAE:", round(mae, 2))
    print("RMSE:", round(rmse, 2))
    print("R2 Score:", round(r2, 4))

# --------------------------------------------------
# 8. SAVE MODEL COMPARISON
# --------------------------------------------------

results_df = pd.DataFrame(results)
results_df = results_df.sort_values(
    by="MAE",
    ascending=True
)

results_file = OUTPUT_FOLDER / "model_evaluation.csv"
results_df.to_csv(results_file, index=False)

best_model_name = results_df.iloc[0]["Model"]

print("\nBest model based on lowest MAE:", best_model_name)

# --------------------------------------------------
# 9. TRAIN BEST MODEL USING ALL HISTORICAL DATA
# --------------------------------------------------

best_algorithm = models[best_model_name]

best_pipeline = Pipeline(
    steps=[
        ("preprocessor", preprocessor),
        ("model", best_algorithm)
    ]
)

best_pipeline.fit(X, y)

# --------------------------------------------------
# 10. CREATE NOVEMBER 2026 PREDICTION DATA
# --------------------------------------------------

food_items = sorted(df["Food_Item"].unique())

forecast_rows = []

current_date = date(2026, 11, 1)
end_date = date(2026, 11, 30)

# These are example calendar markers.
# Update them using your actual canteen holiday calendar.
november_holidays = set()
november_festivals = {}

while current_date <= end_date:

    day_name = current_date.strftime("%A")
    month_name = current_date.strftime("%B")
    weekday_number = current_date.weekday()

    is_weekend = 1 if weekday_number >= 5 else 0
    is_holiday = 1 if current_date.day in november_holidays else 0

    festival = november_festivals.get(
        current_date.day, "None"
    )

    for food_name in food_items:

        forecast_rows.append({
            "Date": current_date.isoformat(),
            "Day": day_name,
            "Month": month_name,
            "Month_Number": current_date.month,
            "Year": current_date.year,
            "Weekday_Number": weekday_number,
            "Is_Weekend": is_weekend,
            "Is_Holiday": is_holiday,
            "Festival": festival,
            "Food_Item": food_name
        })

    current_date += timedelta(days=1)

forecast_df = pd.DataFrame(forecast_rows)

# --------------------------------------------------
# 11. PREDICT FOOD DEMAND
# --------------------------------------------------

forecast_features = forecast_df[feature_columns]

predicted_values = best_pipeline.predict(forecast_features)

forecast_df["Predicted_Quantity"] = (
    np.maximum(0, np.round(predicted_values)).astype(int)
)

forecast_df = forecast_df.rename(
    columns={"Date": "Prediction_Date"}
)

# --------------------------------------------------
# 12. SAVE DAILY PREDICTIONS
# --------------------------------------------------

daily_file = OUTPUT_FOLDER / "november_2026_predictions.csv"

forecast_df.to_csv(daily_file, index=False)

# --------------------------------------------------
# 13. CREATE MONTHLY FOOD-WISE SUMMARY
# --------------------------------------------------

monthly_summary = (
    forecast_df.groupby("Food_Item", as_index=False)
    ["Predicted_Quantity"]
    .sum()
    .sort_values("Predicted_Quantity", ascending=False)
)

monthly_file = OUTPUT_FOLDER / "november_2026_summary.csv"

monthly_summary.to_csv(monthly_file, index=False)

# --------------------------------------------------
# 14. DISPLAY FINAL RESULTS
# --------------------------------------------------

print("\n========== NOVEMBER 2026 PREDICTIONS ==========")

print(monthly_summary.to_string(index=False))

print("\nTotal prediction records:", len(forecast_df))

print("\nFiles saved successfully:")
print("-", results_file)
print("-", daily_file)
print("-", monthly_file)

print("\nMachine learning process completed successfully!")
