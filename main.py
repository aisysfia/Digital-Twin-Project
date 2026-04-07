import pandas as pd
import numpy as np
import joblib
import time
import json # <-- Added JSON import
from sklearn.model_selection import train_test_split, KFold, GridSearchCV
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error
from supabase import create_client, Client

# =================================================================
# PART 1: MODEL TRAINING AND EXPORT
# =================================================================
def train_and_export_model():
    print("--- Starting Model Training ---")
    df = pd.read_csv("EV_cars.csv")
    features = ['Battery', 'Efficiency', 'Fast_charge', 'Top_speed', 'acceleration..0.100.']
    target = 'Range'
    df = df[features + [target]]

    missing_range_mask = df[target].isnull()
    df_missing_range = df[missing_range_mask]
    df_valid_range = df[~missing_range_mask]

    X_valid = df_valid_range[features]
    y_valid = df_valid_range[target]

    X_train, X_test_valid, y_train, y_test_valid = train_test_split(
        X_valid, y_valid, test_size=0.2, random_state=42
    )

    X_test = pd.concat([X_test_valid, df_missing_range[features]])
    y_test = pd.concat([y_test_valid, df_missing_range[target]])

    numeric_features_to_scale = ['Battery', 'Efficiency', 'Fast_charge', 'Top_speed']
    numeric_features_to_passthrough = ['acceleration..0.100.']

    preprocessor = ColumnTransformer(
        transformers=[
            ('scale_features', Pipeline(steps=[
                ('imputer', SimpleImputer(strategy='median')),
                ('scaler', StandardScaler())
            ]), numeric_features_to_scale),
            ('passthrough_features', Pipeline(steps=[
                ('imputer', SimpleImputer(strategy='median'))
            ]), numeric_features_to_passthrough)
        ]
    )

    rf_pipeline = Pipeline(steps=[
        ('preprocessor', preprocessor),
        ('model', RandomForestRegressor(random_state=42))
    ])

    kf = KFold(n_splits=5, shuffle=True, random_state=42)
    param_grid = {
        'model__n_estimators': [50, 100],
        'model__max_depth': [None, 10],
        'model__min_samples_split': [2, 5],
        'model__ccp_alpha': [0.0, 0.01]
    }

    grid_search = GridSearchCV(
        estimator=rf_pipeline,
        param_grid=param_grid,
        cv=kf,
        scoring='neg_mean_squared_error',
        n_jobs=-1
    )

    print("Running Grid Search to find best hyperparameters...")
    grid_search.fit(X_train, y_train)
    best_model_pipeline = grid_search.best_estimator_
    
    valid_test_mask = y_test.notnull()
    X_test_eval = X_test[valid_test_mask]
    y_test_eval = y_test[valid_test_mask]
    y_test_pred = best_model_pipeline.predict(X_test_eval)
    print(f"Test RMSE:  {np.sqrt(mean_squared_error(y_test_eval, y_test_pred)):.4f}")

    model_filename = 'best_rf_model.joblib'
    joblib.dump(best_model_pipeline, model_filename)
    print(f"Model successfully exported as '{model_filename}'\n")

# =================================================================
# PART 2: TELEMETRY PROCESSING AND SUPABASE STREAMING
# =================================================================
def process_and_stream_telemetry():
    print("--- Starting Telemetry Simulation & Database Streaming ---")
    model = joblib.load('best_rf_model.joblib')
    
    # Load your new single-vehicle dataset
    df = pd.read_csv('ai_prediction_telemetry.csv')
    print(f"Loaded {len(df)} rows from the single-vehicle dataset.")

    # 1. PREDICT RANGE
    features = df[['Battery', 'Efficiency', 'Fast_charge', 'Top_speed', 'acceleration..0.100.']]
    predicted_ranges = model.predict(features)
    time_sec = df['time_sec'].values

    # 2. DERIVE SPEED AND SOC FOR DASHBOARD/OMNIVERSE
    # Simulate a smooth physical speed in km/h (peaking around 90 km/h)
    t = np.linspace(0, 15, len(df))
    speed_kmh = np.abs(np.sin(t) * 90) + np.random.normal(0, 0.8, len(df))
    
    # Convert raw Battery capacity back into a 0-100% State of Charge
    max_battery = df['Battery'].max()
    battery_status = (df['Battery'] / max_battery) * 100.0

    # 3. EXPORT FILES FOR OMNIVERSE
    np.savetxt('time_sec.txt', time_sec, fmt='%.3f')
    np.savetxt('speed_kmh.txt', speed_kmh, fmt='%.2f') # Updated file name
    np.savetxt('battery_status.txt', battery_status.values, fmt='%.4f')
    np.savetxt('predicted_range.txt', predicted_ranges, fmt='%.2f')
    print("Successfully exported .txt files for NVIDIA Omniverse.")

    # 4. STREAM TO SUPABASE
    print("Connecting to Supabase...")
    url = "https://cswbueyxdlonazgsnmll.supabase.co"
    key = "sb_publishable_pz2zbAD3gMdydjF3oXfcow_AjhCvnBb"
    
    try:
        supabase: Client = create_client(url, key)
    except Exception as e:
        print(f"Failed to connect to Supabase. Check your URL and Key. Error: {e}")
        return

    print("Streaming telemetry to Supabase (simulating real-time)...")
    for i in range(len(predicted_ranges)):
        data = {
            "time_sec": float(time_sec[i]),
            "speed_kmh": float(speed_kmh[i]), # Updated column key
            "battery_status": float(battery_status.iloc[i]),
            "predicted_range": float(predicted_ranges[i])
        }
        
        # --- NEW CODE: Write the latest data to a local JSON file for Omniverse ---
        with open("live_telemetry.json", "w") as f:
            json.dump(data, f)
        # ------------------------------------------------------------
        
        try:
            supabase.table('ev_telemetry').insert(data).execute()
            print(f"Pushed row {i+1}/{len(predicted_ranges)}: Range {data['predicted_range']:.2f} km")
        except Exception as e:
            print(f"Failed to push row {i+1}: {e}")
            
        time.sleep(0.5) 

    print("Supabase streaming complete!")

# =================================================================
# MAIN EXECUTION
# =================================================================
if __name__ == '__main__':
    train_and_export_model()
    process_and_stream_telemetry()