# ============================================================
# FRAUD DETECTION SYSTEM -- FINAL VERSION
# ============================================================
# Key upgrades:
#
#   1. FIXED TRAIN/TEST SPLIT — saved to split_indices.pkl
#      - First run  → creates and saves split by row index
#      - Every run after → reloads EXACT same split
#      - Test set permanently frozen, never seen during training
#      - Accuracy numbers are truly reproducible across runs
#
#   2. HITL SAMPLE ROUTING
#      - Admin labels UNCERTAIN cases via portal
#      - append_to_dataset() adds them to master_dataset.csv
#      - New rows have indices OUTSIDE original split
#      - Pipeline detects them and routes to training ONLY
#      - Test set never contaminated by human-labeled data
#      - Model genuinely improves from admin feedback
# ============================================================

import os
import pandas as pd
import numpy as np
import re
import pickle
from itertools import product

from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline, FeatureUnion
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import MultinomialNB
from sklearn.svm import LinearSVC
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import (
    classification_report, confusion_matrix,
    accuracy_score, f1_score, roc_auc_score
)

# ============================================================
# CONSTANTS
# ============================================================

RANDOM_STATE = 42       # fixed forever — never change this
SPLIT_FILE   = "split_indices.pkl"

CUSTOM_STOPWORDS = [
    "the","is","in","it","of","and","to","a","that","this","for","on",
    "are","with","as","at","be","by","from","or","an","was","were",
    "have","has","had","will","would","could","should","may","might",
    "do","did","does","been","being","i","me","my","we","our","you",
    "your","he","she","they","his","her","their","its","not","no",
    "so","but","if","about","which","who","what","when","where",
    "how","all","can","just","than","then","also","more","some","any",
    "there","here","into","up","out","said","get","got",
    "love","health","thanks","university","http","pm","hi","hello",
    "dear","sir","please","now","new","good","time","day","name",
    "old","years","am","year"
]

CONVERSATIONAL_PATTERNS = [
    r'^(hi|hey|hello|good morning|good night|gm|gn)\b.{0,40}$',
    r'^how are you',
    r'^(ok|okay|sure|thanks|thank you|noted|got it)\s*[.!]?$',
]

# ============================================================
# PURE FUNCTIONS
# ============================================================

def preprocess(text):
    """
    Normalise raw message for vectoriser input.
    CRITICAL: Must stay identical in app.py and pipefinal.py.
    Any change here requires full retraining from scratch.
    """
    text = str(text).lower()
    text = re.sub(r'http\S+|www\.\S+',   ' SUSPICIOUS_URL ',   text)
    text = re.sub(r'\b[789]\d{9}\b',      ' PHONE_NUMBER ',     text)
    text = re.sub(r'rs\.?\s*\d[\d,]+',    ' MONEY_AMOUNT ',     text)
    text = re.sub(r'\$\s*\d[\d,]+',       ' MONEY_AMOUNT_USD ', text)
    text = re.sub(r'\b\d{4,6}\b',         ' OTP_NUMBER ',       text)
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def is_conversational(text):
    t = text.lower().strip()
    for pattern in CONVERSATIONAL_PATTERNS:
        if re.match(pattern, t):
            return True
    return False


if __name__ == '__main__':

    # ----------------------------------------------------------
    # 1. LOAD DATA
    # ----------------------------------------------------------

    df = pd.read_csv("master_dataset.csv")
    df = df[['text', 'label']].dropna().drop_duplicates()
    df['label'] = df['label'].astype(int)
    df = df.reset_index(drop=True)   # clean 0-based index — required for split

    print(f"Total samples  : {len(df)}")
    print(f"Fraud (1)      : {df['label'].sum()}")
    print(f"Legit (0)      : {(df['label'] == 0).sum()}")
    print(f"Fraud ratio    : {df['label'].mean():.2%}\n")

    # ----------------------------------------------------------
    # 2. PREPROCESS
    # ----------------------------------------------------------

    df["clean_text"] = df["text"].apply(preprocess)

    X = df["clean_text"]
    y = df["label"]

    # ----------------------------------------------------------
    # 3. FIXED TRAIN / VAL / TEST SPLIT
    #
    #    HOW IT WORKS:
    #    First run:
    #      - Creates 70/15/15 stratified split
    #      - Saves row indices to split_indices.pkl
    #      - These indices are frozen permanently
    #
    #    Every subsequent run (including after HITL retraining):
    #      - Reloads exact same indices from split_indices.pkl
    #      - Detects any NEW rows added by admin via portal
    #      - Routes new rows to training set ONLY
    #      - Test set never changes — results are comparable
    #
    #    HITL flow:
    #      Admin labels UNCERTAIN case in portal
    #      → append_to_dataset() adds row to master_dataset.csv
    #      → New row gets index BEYOND original split range
    #      → This pipeline detects it as "new_indices"
    #      → Added to train only, test stays frozen
    # ----------------------------------------------------------

    if os.path.exists(SPLIT_FILE):
        # ── Reload existing split ──────────────────────────────
        print(f"Loading existing split from {SPLIT_FILE}")
        print("Same split reused — test set permanently frozen.\n")

        with open(SPLIT_FILE, "rb") as f:
            split_indices = pickle.load(f)

        train_idx = split_indices["train"]
        val_idx   = split_indices["val"]
        test_idx  = split_indices["test"]

        # Safety check — warn if original indices missing
        all_idx       = set(df.index.tolist())
        missing_train = set(train_idx) - all_idx
        missing_val   = set(val_idx)   - all_idx
        missing_test  = set(test_idx)  - all_idx

        if missing_train or missing_val or missing_test:
            print(f"WARNING: {len(missing_train)} train, "
                  f"{len(missing_val)} val, "
                  f"{len(missing_test)} test indices missing from dataset.")
            print("Dataset may have changed. "
                  "Delete split_indices.pkl to recreate.\n")

        # ── HITL sample routing ────────────────────────────────
        # Any row index outside original split = new HITL sample
        # Route to training only — never val or test
        original_indices = set(train_idx + val_idx + test_idx)
        new_indices      = [
            i for i in df.index.tolist()
            if i not in original_indices
        ]

        if new_indices:
            print(f"Found {len(new_indices)} new HITL-labeled sample(s)")
            print(f"Adding to training set only — test set unchanged.")
            print(f"Train: {len(train_idx)} -> {len(train_idx) + len(new_indices)}\n")
            train_idx = train_idx + new_indices
        else:
            print("No new HITL samples found.\n")

        X_train = X.loc[train_idx]
        y_train = y.loc[train_idx]
        X_val   = X.loc[val_idx]
        y_val   = y.loc[val_idx]
        X_test  = X.loc[test_idx]
        y_test  = y.loc[test_idx]

    else:
        # ── First run — create and save split ──────────────────
        print(f"No split file found.")
        print(f"Creating new split (random_state={RANDOM_STATE})")
        print(f"Saving to {SPLIT_FILE} — all future runs reuse this.\n")

        X_train, X_temp, y_train, y_temp = train_test_split(
            X, y, test_size=0.30,
            stratify=y, random_state=RANDOM_STATE
        )
        X_val, X_test, y_val, y_test = train_test_split(
            X_temp, y_temp, test_size=0.50,
            stratify=y_temp, random_state=RANDOM_STATE
        )

        split_indices = {
            "train": X_train.index.tolist(),
            "val":   X_val.index.tolist(),
            "test":  X_test.index.tolist(),
        }

        with open(SPLIT_FILE, "wb") as f:
            pickle.dump(split_indices, f)

        print(f"Split saved to {SPLIT_FILE}\n")

    print(f"Train : {len(X_train):,} | Val : {len(X_val):,} | Test : {len(X_test):,}")
    print(f"Train fraud : {y_train.mean():.2%} | "
          f"Val fraud   : {y_val.mean():.2%} | "
          f"Test fraud  : {y_test.mean():.2%}\n")

    # ----------------------------------------------------------
    # 4. VECTORIZE — fit ONCE on train only, frozen after this
    # ----------------------------------------------------------

    print("Vectorizing...")

    word_vectorizer = TfidfVectorizer(
        ngram_range=(1, 2), min_df=3, max_df=0.85,
        stop_words=CUSTOM_STOPWORDS, max_features=20000, sublinear_tf=True
    )
    char_vectorizer = TfidfVectorizer(
        analyzer='char_wb', ngram_range=(3, 5),
        max_features=5000, min_df=2
    )
    vectorizer = FeatureUnion([("word", word_vectorizer), ("char", char_vectorizer)])

    X_train_vec = vectorizer.fit_transform(X_train)
    X_val_vec   = vectorizer.transform(X_val)
    X_test_vec  = vectorizer.transform(X_test)

    print(f"Vectorizer fitted. Features: {X_train_vec.shape[1]:,}\n")

    # ----------------------------------------------------------
    # 5. TRAIN BASE MODELS
    # ----------------------------------------------------------

    print("Training base models...")

    lr = LogisticRegression(
        max_iter=1000, C=0.5,
        class_weight={0: 1.0, 1: 1.5},
        solver='lbfgs'
    )
    nb      = MultinomialNB(alpha=0.1)
    svm_cal = CalibratedClassifierCV(
        LinearSVC(class_weight='balanced', max_iter=2000, C=0.8),
        method='sigmoid', cv=3
    )

    lr.fit(X_train_vec, y_train)
    nb.fit(X_train_vec, y_train)
    svm_cal.fit(X_train_vec, y_train)

    print("Base models trained.\n")

    # ----------------------------------------------------------
    # 6. TUNE ENSEMBLE WEIGHTS ON VALIDATION SET
    # ----------------------------------------------------------

    print("Tuning ensemble weights on validation set...")

    p_lr_val  = lr.predict_proba(X_val_vec)
    p_nb_val  = nb.predict_proba(X_val_vec)
    p_svm_val = svm_cal.predict_proba(X_val_vec)

    best_f1      = 0.0
    best_weights = (0.5, 0.3, 0.2)
    candidates   = [round(w * 0.1, 1) for w in range(1, 8)]

    for w1, w2, w3 in product(candidates, repeat=3):
        if abs(w1 + w2 + w3 - 1.0) > 0.01:
            continue
        blended = w1 * p_lr_val + w2 * p_svm_val + w3 * p_nb_val
        preds   = (blended[:, 1] > 0.5).astype(int)
        f1      = f1_score(y_val, preds, average='macro')
        if f1 > best_f1:
            best_f1      = f1
            best_weights = (w1, w2, w3)

    W_LR, W_SVM, W_NB = best_weights
    print(f"Best weights -> LR: {W_LR}, SVM: {W_SVM}, NB: {W_NB}  "
          f"(val macro-F1: {best_f1:.4f})\n")

    def ensemble_proba(X_vec):
        p1 = lr.predict_proba(X_vec)
        p2 = nb.predict_proba(X_vec)
        p3 = svm_cal.predict_proba(X_vec)
        return W_LR * p1 + W_SVM * p3 + W_NB * p2

    # ----------------------------------------------------------
    # 7. PRE-RETRAIN EVALUATION (val set)
    # ----------------------------------------------------------

    print("--- RESULTS BEFORE HARD NEGATIVE RETRAINING (on val set) ---")

    probs_before  = ensemble_proba(X_val_vec)
    y_pred_before = (probs_before[:, 1] > 0.5).astype(int)

    print(f"Accuracy  : {accuracy_score(y_val, y_pred_before):.4f}")
    print(f"ROC-AUC   : {roc_auc_score(y_val, probs_before[:, 1]):.4f}")
    print(classification_report(y_val, y_pred_before, target_names=['Legit', 'Fraud']))
    print("Confusion Matrix:")
    print(confusion_matrix(y_val, y_pred_before))
    print()

    # ----------------------------------------------------------
    # 8. HARD NEGATIVE RETRAINING
    # ----------------------------------------------------------

    print("Mining False Positives from validation set...")

    # 1. True Hard Negative Mining: Only False Positives
    # Actual Legit (0) -> Predicted Fraud (1)
    false_positives_mask = (y_val.values == 0) & (y_pred_before == 1)
    fp_indices = np.where(false_positives_mask)[0]
    
    # 2. Confidence-based filtering
    fp_probs = probs_before[false_positives_mask, 1]
    sorted_idx_by_prob = np.argsort(fp_probs)[::-1]
    sorted_fp_indices = fp_indices[sorted_idx_by_prob]
    
    # 3. Top 15% hardest samples
    top_k = max(1, int(len(sorted_fp_indices) * 0.15))
    hardest_fp_indices = sorted_fp_indices[:top_k]
    
    hard_texts  = X_val.iloc[hardest_fp_indices].tolist()
    hard_labels = y_val.iloc[hardest_fp_indices].tolist()

    print(f"Total False Positives: {len(fp_indices)}")
    print(f"Top 15% Hard Examples kept: {len(hard_texts)}\n")

    # 4. Weighted retraining
    X_aug     = list(X_train) + hard_texts
    y_aug     = list(y_train) + hard_labels
    X_aug_vec = vectorizer.transform(X_aug)   # vectorizer NOT re-fit
    
    # Base weight 1.0, Hard Negative weight 2.0
    weights = [1.0] * len(X_train) + [2.0] * len(hard_texts)

    lr.fit(X_aug_vec, y_aug, sample_weight=weights)
    nb.fit(X_aug_vec, y_aug, sample_weight=weights)
    svm_cal.fit(X_aug_vec, y_aug, sample_weight=weights)

    print("False-Positive-Driven Hard negative retraining complete.\n")

    # ----------------------------------------------------------
    # 9. FINAL EVALUATION ON UNTOUCHED TEST SET
    # ----------------------------------------------------------

    print("--- FINAL RESULTS ON TEST SET ---")

    probs_final  = ensemble_proba(X_test_vec)
    y_pred_final = (probs_final[:, 1] > 0.5).astype(int)

    print(f"Accuracy   : {accuracy_score(y_test, y_pred_final):.4f}")
    print(f"ROC-AUC    : {roc_auc_score(y_test, probs_final[:, 1]):.4f}")
    print(classification_report(y_test, y_pred_final, target_names=['Legit', 'Fraud']))
    print("Confusion Matrix:")
    print(confusion_matrix(y_test, y_pred_final))
    print()

    print("--- THRESHOLD SENSITIVITY (on test set) ---")
    print(f"{'Threshold':<12} {'Precision':>10} {'Recall':>8} {'F1 (Fraud)':>12}")
    for threshold in [0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60]:
        preds  = (probs_final[:, 1] > threshold).astype(int)
        report = classification_report(
            y_test, preds, output_dict=True, zero_division=0
        )
        fraud  = report.get('1', {})
        print(f"{threshold:<12.2f} {fraud.get('precision',0):>10.4f} "
              f"{fraud.get('recall',0):>8.4f} {fraud.get('f1-score',0):>12.4f}")
    print()

    # ----------------------------------------------------------
    # 10. CROSS-VALIDATION
    # ----------------------------------------------------------

    print("Running 5-fold stratified cross-validation (LR baseline)...")

    cv_pipeline = Pipeline([
        ('tfidf', TfidfVectorizer(
            ngram_range=(1, 2), min_df=3, max_df=0.85,
            stop_words=CUSTOM_STOPWORDS, max_features=20000, sublinear_tf=True
        )),
        ('clf', LogisticRegression(
            max_iter=1000, C=0.5,
            class_weight={0: 1.0, 1: 1.5}, solver='lbfgs'
        ))
    ])

    skf    = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    scores = cross_val_score(
        cv_pipeline, X, y,
        cv=skf, scoring='f1_macro',
        n_jobs=1
    )

    print(f"CV Macro F1: {scores.mean():.4f} ± {scores.std():.4f}")
    print(f"Per-fold   : {[round(float(s), 4) for s in scores]}\n")

    # ----------------------------------------------------------
    # 11. SAVE MODEL ARTIFACTS
    # ----------------------------------------------------------

    with open("final_vectorizer.pkl", "wb") as f:
        pickle.dump(vectorizer, f)

    with open("final_models.pkl", "wb") as f:
        pickle.dump({
            "lr"      : lr,
            "nb"      : nb,
            "svm"     : svm_cal,
            "weights" : best_weights
        }, f)

    print("Model saved  -> final_vectorizer.pkl + final_models.pkl")
    print(f"Split saved  -> {SPLIT_FILE}")
    print("             (delete ONLY to reset split — loses reproducibility)\n")
    print("Training pipeline completed successfully.")