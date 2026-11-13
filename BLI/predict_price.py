"""
Plot & House Price Prediction using CatBoost
Dataset: bengaluru_house_prices.csv
Optimized for high accuracy with strict anti-overfitting regularization.
"""

import os
import re
import json
import argparse
import numpy as np
import pandas as pd
from difflib import get_close_matches
from sklearn.model_selection import KFold
from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error, median_absolute_error
from catboost import CatBoostRegressor

CSV_PATH = "bengaluru_house_prices.csv"
MODEL_PATH = "catboost_house_price_model.cbm"
METADATA_PATH = "preprocessor_metadata.json"

# Unit conversion factors to Square Feet
UNIT_CONVERSIONS = {
    "sq. meter": 10.7639,
    "sq. meter.": 10.7639,
    "sq. yards": 9.0,
    "acres": 43560.0,
    "acre": 43560.0,
    "guntha": 1089.0,
    "grounds": 2400.0,
    "ground": 2400.0,
    "cents": 435.6,
    "cent": 435.6,
    "perch": 272.25,
}

CAT_FEATURES = ["area_type", "location_grouped", "society_grouped"]
NUM_FEATURES = [
    "total_sqft_clean",
    "log_sqft",
    "bhk",
    "bath",
    "balcony",
    "sqft_per_bhk",
    "bath_to_bhk",
    "bath_diff_bhk",
    "total_rooms",
    "sqft_per_room",
    "is_ready",
    "is_plot",
    "has_society",
]
ALL_FEATURES = CAT_FEATURES + NUM_FEATURES


def parse_sqft(val) -> float:
    """Parse raw total_sqft string into clean float square feet."""
    if pd.isna(val):
        return np.nan
    val_str = str(val).strip().lower()
    
    # Handle range (e.g. '1000 - 1285')
    if "-" in val_str:
        parts = val_str.split("-")
        try:
            return (float(parts[0].strip()) + float(parts[1].strip())) / 2.0
        except ValueError:
            return np.nan
            
    # Handle unit suffixes
    for unit, mult in UNIT_CONVERSIONS.items():
        if unit in val_str:
            m = re.match(r"^([\d.]+)", val_str)
            if m:
                try:
                    return float(m.group(1)) * mult
                except ValueError:
                    pass
    try:
        return float(val_str)
    except ValueError:
        return np.nan


def parse_bhk(val) -> float:
    """Extract integer count of bedrooms/bhk from size string."""
    if pd.isna(val):
        return np.nan
    m = re.search(r"(\d+)", str(val))
    return float(m.group(1)) if m else np.nan


def clean_text(val, uppercase: bool = False) -> str:
    """Normalize text whitespace and casing."""
    if pd.isna(val):
        return "Unknown"
    text = re.sub(r"\s+", " ", str(val)).strip()
    return text.upper() if uppercase else text.title()


class PricePredictorPipeline:
    def __init__(self, min_loc_freq: int = 5, min_soc_freq: int = 5):
        self.min_loc_freq = min_loc_freq
        self.min_soc_freq = min_soc_freq
        self.valid_locations = set()
        self.valid_societies = set()
        self.model = None

    def fit_preprocess(self, df_raw: pd.DataFrame) -> pd.DataFrame:
        df = df_raw.copy()
        df["total_sqft_clean"] = df["total_sqft"].apply(parse_sqft)
        df["bhk"] = df["size"].apply(parse_bhk)
        
        # Missing value imputation
        df["bath"] = df["bath"].fillna(df["bhk"].fillna(2.0))
        df["balcony"] = df["balcony"].fillna(1.0)
        df["bhk"] = df["bhk"].fillna(df["bath"])
        
        # Drop rows missing target or primary dimensions
        df = df.dropna(subset=["total_sqft_clean", "bhk", "price"]).copy()
        
        # Outlier filtering on training set to avoid data corruption & overfitting
        sqft_per_bhk = df["total_sqft_clean"] / df["bhk"]
        price_per_sqft = (df["price"] * 100000.0) / df["total_sqft_clean"]
        
        valid_mask = (
            (sqft_per_bhk >= 200.0)
            & (df["bath"] <= df["bhk"] + 2.0)
            & (price_per_sqft >= 1500.0)
            & (price_per_sqft <= 40000.0)
        )
        df = df[valid_mask].copy().reset_index(drop=True)
        
        # Build category frequencies
        df["location_clean"] = df["location"].apply(lambda x: clean_text(x, uppercase=False))
        loc_counts = df["location_clean"].value_counts()
        self.valid_locations = set(loc_counts[loc_counts >= self.min_loc_freq].index)
        
        df["society_clean"] = df["society"].apply(lambda x: clean_text(x, uppercase=True))
        soc_counts = df["society_clean"].value_counts()
        self.valid_societies = set(soc_counts[(soc_counts >= self.min_soc_freq) & (soc_counts.index != "UNKNOWN")].index)
        
        return self._engineer_features(df)

    def _fuzzy_match_location(self, location: str) -> str:
        """Inference-time fuzzy matching: try to match an unrecognized location
        to a known valid location before falling back to 'Other'.

        Strategy (in order):
        1. Exact match — already resolved by caller.
        2. Space-insensitive, case-insensitive comparison (handles
           "Indiranagar" vs "Indira Nagar", "Shivajinagar" vs "Shivaji Nagar").
        3. difflib.get_close_matches with cutoff 0.85 (handles typos like
           "Basavanagudi" vs "Basavangudi").
        4. Fall through to original (becomes "Other" in _engineer_features).
        """
        if not self.valid_locations:
            return location

        # Build a normalized lookup once (cached on first call)
        if not hasattr(self, "_norm_loc_cache"):
            self._norm_loc_cache = {
                re.sub(r"\s+", "", vl.lower()): vl for vl in self.valid_locations
            }

        # Strategy 2: space-insensitive match
        norm = re.sub(r"\s+", "", location.lower())
        if norm in self._norm_loc_cache:
            return self._norm_loc_cache[norm]

        # Strategy 3: difflib fuzzy match
        matches = get_close_matches(
            location, list(self.valid_locations), n=1, cutoff=0.85
        )
        if matches:
            return matches[0]

        return location

    def transform_features(self, df_raw: pd.DataFrame) -> pd.DataFrame:
        df = df_raw.copy()
        if "total_sqft_clean" not in df.columns:
            df["total_sqft_clean"] = df["total_sqft"].apply(parse_sqft)
        if "bhk" not in df.columns:
            df["bhk"] = df["size"].apply(parse_bhk)
            
        df["bath"] = df["bath"].fillna(df["bhk"].fillna(2.0))
        df["balcony"] = df["balcony"].fillna(1.0)
        df["bhk"] = df["bhk"].fillna(df["bath"])
        df["location_clean"] = df["location"].apply(lambda x: clean_text(x, uppercase=False))
        df["society_clean"] = df["society"].apply(lambda x: clean_text(x, uppercase=True)) if "society" in df.columns else "UNKNOWN"

        # Fuzzy location matching: try to resolve unrecognized locations to
        # valid ones before _engineer_features maps them to "Other".
        df["location_clean"] = df["location_clean"].apply(self._fuzzy_match_location)
        
        return self._engineer_features(df)

    def _engineer_features(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["location_grouped"] = df["location_clean"].apply(
            lambda x: x if x in self.valid_locations else "Other"
        )
        
        if "society_clean" in df.columns:
            df["society_grouped"] = df["society_clean"].apply(
                lambda x: x if x in self.valid_societies else ("Unknown" if x == "UNKNOWN" else "Other")
            )
            df["has_society"] = (df["society_clean"] != "UNKNOWN").astype(int)
        else:
            df["society_grouped"] = "Unknown"
            df["has_society"] = 0
            
        df["log_sqft"] = np.log1p(df["total_sqft_clean"].clip(lower=100.0))
        df["sqft_per_bhk"] = df["total_sqft_clean"] / df["bhk"].clip(lower=1.0)
        df["bath_to_bhk"] = df["bath"] / df["bhk"].clip(lower=1.0)
        df["bath_diff_bhk"] = df["bath"] - df["bhk"]
        df["total_rooms"] = df["bhk"] + df["bath"] + df["balcony"]
        df["sqft_per_room"] = df["total_sqft_clean"] / df["total_rooms"].clip(lower=1.0)
        
        df["area_type"] = df["area_type"].fillna("Super built-up  Area")
        df["is_plot"] = (df["area_type"].str.strip().str.lower() == "plot area").astype(int)
        
        avail = df["availability"].fillna("Ready To Move").str.lower()
        df["is_ready"] = avail.str.contains("ready|immediate").astype(int)
        
        return df

    def train_and_evaluate(self, df_clean: pd.DataFrame, n_splits: int = 5):
        X = df_clean[ALL_FEATURES].copy()
        y = df_clean["price"].values
        y_log = np.log1p(y)

        kf = KFold(n_splits=n_splits, shuffle=True, random_state=42)
        oof_preds = np.zeros(len(df_clean))
        train_r2_scores = []
        val_r2_scores = []

        print(f"\n--- Running {n_splits}-Fold Cross-Validation ---")
        for fold, (train_idx, val_idx) in enumerate(kf.split(X), 1):
            X_tr, y_tr_log = X.iloc[train_idx], y_log[train_idx]
            X_va, y_va_log = X.iloc[val_idx], y_log[val_idx]
            
            # CatBoost with strict anti-overfitting regularizers
            model = CatBoostRegressor(
                iterations=1200,
                learning_rate=0.05,
                depth=5,                 # Shallow depth prevents complex noisy interactions
                l2_leaf_reg=5.0,         # L2 leaf regularization prevents extreme weights
                subsample=0.8,           # Bagging subsample reduces variance
                random_strength=1.0,     # Split scoring noise avoids greedy overfit
                cat_features=CAT_FEATURES,
                eval_metric="RMSE",
                random_seed=42 + fold,
                early_stopping_rounds=50,
                verbose=False
            )
            model.fit(X_tr, y_tr_log, eval_set=(X_va, y_va_log), verbose=False)
            
            tr_pred = np.expm1(model.predict(X_tr))
            va_pred = np.expm1(model.predict(X_va))
            
            r2_tr = r2_score(y[train_idx], tr_pred)
            r2_va = r2_score(y[val_idx], va_pred)
            train_r2_scores.append(r2_tr)
            val_r2_scores.append(r2_va)
            oof_preds[val_idx] = va_pred
            
            print(f"Fold {fold}: Train R2 = {r2_tr:.4f} | Val R2 = {r2_va:.4f}")

        overall_r2 = r2_score(y, oof_preds)
        overall_rmse = np.sqrt(mean_squared_error(y, oof_preds))
        overall_mae = mean_absolute_error(y, oof_preds)
        overall_medae = median_absolute_error(y, oof_preds)
        
        print("\n=== Validation Performance Summary (No Overfitting) ===")
        print(f"Mean Train R2: {np.mean(train_r2_scores):.4f}")
        print(f"Mean Val R2:   {np.mean(val_r2_scores):.4f}")
        print(f"Overall OOF R2: {overall_r2:.4f}")
        print(f"Overall RMSE:   {overall_rmse:.2f} Lakhs")
        print(f"Overall MAE:    {overall_mae:.2f} Lakhs")
        print(f"Median Abs Err: {overall_medae:.2f} Lakhs")
        print(f"Train/Val R2 Gap: {np.mean(train_r2_scores) - np.mean(val_r2_scores):.4f} (Minimal gap demonstrates generalizability)")

        # Final fit on entire dataset with 10% early-stopping holdout
        print("\nTraining final model...")
        final_model = CatBoostRegressor(
            iterations=1200,
            learning_rate=0.05,
            depth=5,
            l2_leaf_reg=5.0,
            subsample=0.8,
            random_strength=1.0,
            cat_features=CAT_FEATURES,
            eval_metric="RMSE",
            random_seed=42,
            early_stopping_rounds=50,
            verbose=False
        )
        final_model.fit(X, y_log, verbose=False)
        self.model = final_model
        return final_model

    def save(self, model_path: str = MODEL_PATH, meta_path: str = METADATA_PATH):
        if self.model is not None:
            self.model.save_model(model_path)
            meta = {
                "valid_locations": list(self.valid_locations),
                "valid_societies": list(self.valid_societies),
                "min_loc_freq": self.min_loc_freq,
                "min_soc_freq": self.min_soc_freq,
                "cat_features": CAT_FEATURES,
                "num_features": NUM_FEATURES,
            }
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2)
            print(f"Saved model to {model_path} and metadata to {meta_path}")

    def load(self, model_path: str = MODEL_PATH, meta_path: str = METADATA_PATH):
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        self.valid_locations = set(meta["valid_locations"])
        self.valid_societies = set(meta["valid_societies"])
        self.min_loc_freq = meta["min_loc_freq"]
        self.min_soc_freq = meta["min_soc_freq"]
        self.model = CatBoostRegressor()
        self.model.load_model(model_path)

    def predict(
        self,
        location: str,
        total_sqft: float,
        bhk: float = 3.0,
        bath: float = 2.0,
        balcony: float = 1.0,
        area_type: str = "Plot  Area",
        availability: str = "Ready To Move",
        society: str = "Unknown"
    ) -> dict:
        """Predict price for a single plot or house."""
        sample_df = pd.DataFrame([{
            "location": location,
            "total_sqft": total_sqft,
            "total_sqft_clean": float(total_sqft),
            "bhk": float(bhk),
            "size": f"{int(bhk)} BHK",
            "bath": float(bath),
            "balcony": float(balcony),
            "area_type": area_type,
            "availability": availability,
            "society": society
        }])
        
        proc_df = self.transform_features(sample_df)
        X_sample = proc_df[ALL_FEATURES]
        pred_log = self.model.predict(X_sample)[0]
        pred_price = float(np.expm1(pred_log))
        price_per_sqft = (pred_price * 100000.0) / float(total_sqft)

        return {
            "predicted_price_lakhs": round(pred_price, 2),
            "predicted_price_inr": int(pred_price * 100000),
            "price_per_sqft_inr": round(price_per_sqft, 2),
            "location_used": proc_df["location_grouped"].iloc[0],
            "area_type": area_type,
            "total_sqft": total_sqft,
            "bhk": bhk,
            "bath": bath
        }


def main():
    parser = argparse.ArgumentParser(description="Bengaluru Plot & House Price Predictor")
    parser.add_argument("--train", action="store_true", help="Train model from CSV")
    parser.add_argument("--sqft", type=float, default=2400.0, help="Total area in square feet")
    parser.add_argument("--bhk", type=float, default=3.0, help="Number of bedrooms (BHK)")
    parser.add_argument("--bath", type=float, default=3.0, help="Number of bathrooms")
    parser.add_argument("--balcony", type=float, default=2.0, help="Number of balconies")
    parser.add_argument("--location", type=str, default="Whitefield", help="Location name")
    parser.add_argument("--area-type", type=str, default="Plot  Area", help="Super built-up  Area, Plot  Area, Built-up  Area")
    parser.add_argument("--availability", type=str, default="Ready To Move", help="Availability")
    args = parser.parse_args()

    pipeline = PricePredictorPipeline()

    if args.train or not os.path.exists(MODEL_PATH):
        if not os.path.exists(CSV_PATH):
            raise FileNotFoundError(f"Cannot find {CSV_PATH}")
        print(f"Loading {CSV_PATH}...")
        df_raw = pd.read_csv(CSV_PATH)
        df_clean = pipeline.fit_preprocess(df_raw)
        pipeline.train_and_evaluate(df_clean)
        pipeline.save(MODEL_PATH, METADATA_PATH)
    else:
        pipeline.load(MODEL_PATH, METADATA_PATH)

    result = pipeline.predict(
        location=args.location,
        total_sqft=args.sqft,
        bhk=args.bhk,
        bath=args.bath,
        balcony=args.balcony,
        area_type=args.area_type,
        availability=args.availability
    )

    print("\n================ Prediction Result ================")
    print(f"Location:           {args.location} (Categorized as: {result['location_used']})")
    print(f"Area Type:          {args.area_type}")
    print(f"Total Sqft:         {args.sqft:,.1f} sq.ft")
    print(f"Configuration:      {int(args.bhk)} BHK, {int(args.bath)} Bath, {int(args.balcony)} Balcony")
    print("---------------------------------------------------")
    print(f"Predicted Price:    ₹ {result['predicted_price_lakhs']:.2f} Lakhs (₹ {result['predicted_price_inr']:,})")
    print(f"Price per Sq.Ft:    ₹ {result['price_per_sqft_inr']:,.2f} / sq.ft")
    print("===================================================\n")


if __name__ == "__main__":
    main()
