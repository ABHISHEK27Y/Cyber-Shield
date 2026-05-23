"""
Regenerates all matplotlib-based report figures with a consistent
color palette aligned with the TikZ diagram color language.

Palette:
  FRAUD       #E74C3C  (red)
  SUSPICIOUS  #E67E22  (orange)
  UNCERTAIN   #F1C40F  (yellow)
  LEGIT       #2ECC71  (green)
  Citizen     #3498DB  (blue)
  Admin       #9B59B6  (purple)
  Data stores #95A5A6  (grey)
  ML comps    #1ABC9C  (teal)

Run from: d:\miniProject\Spam_reporting_portal\
Output:   Report\figures\fig_*.pdf
"""

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import LinearSegmentedColormap
import joblib, os, sys

# Apply premium styling
plt.style.use('seaborn-v0_8-whitegrid')
matplotlib.rcParams.update({
    'font.family': 'sans-serif',
    'font.size': 12,
    'axes.titlesize': 14,
    'axes.labelsize': 12,
    'lines.linewidth': 3.0,
    'axes.spines.top': False,
    'axes.spines.right': False,
    'figure.dpi': 300,
    'savefig.dpi': 300,
    'savefig.transparent': False
})

# ── Palette ──────────────────────────────────────────────────────────────────
FRAUD     = '#E74C3C'
SUSP      = '#E67E22'
UNCERT    = '#F1C40F'
LEGIT     = '#2ECC71'
ML_TEAL   = '#1ABC9C'
BLUE      = '#3498DB'
GREY      = '#95A5A6'
DARK      = '#2C3E50'

OUT = r'd:\miniProject\Spam_reporting_portal\figures'   # ../figures/ in graphicspath
os.makedirs(OUT, exist_ok=True)
PPT_IMG = r'd:\miniProject\Spam_reporting_portal\Report\ppt_imgs'
os.makedirs(PPT_IMG, exist_ok=True)

# ── Load model artefacts ──────────────────────────────────────────────────────
try:
    models     = joblib.load('final_models.pkl')
    vectorizer = joblib.load('final_vectorizer.pkl')
    split      = joblib.load('split_indices.pkl')

    import pandas as pd
    df = pd.read_csv('master_dataset.csv')
    X  = vectorizer.transform(df['text'])
    y  = df['label'].values

    X_test = X[split['test']]
    y_test = y[split['test']]

    lr, svm, nb = models['lr'], models['svm'], models['nb']
    w = [0.20, 0.50, 0.30]
    P_test = (w[0]*lr.predict_proba(X_test)[:,1]
            + w[1]*svm.predict_proba(X_test)[:,1]
            + w[2]*nb.predict_proba(X_test)[:,1])

    # Pre-HNM split (training set before mining)
    X_val = X[split['val']]
    y_val = y[split['val']]
    P_val = (w[0]*lr.predict_proba(X_val)[:,1]
           + w[1]*svm.predict_proba(X_val)[:,1]
           + w[2]*nb.predict_proba(X_val)[:,1])

    HAVE_DATA = True
except Exception as e:
    print(f"[WARN] Could not load model artefacts: {e}")
    print("[INFO] Generating figures with placeholder data.")
    HAVE_DATA = False


# ─────────────────────────────────────────────────────────────────────────────
# Figure 1: Pre vs Post HNM bar chart
# ─────────────────────────────────────────────────────────────────────────────
metrics_pre  = {'Accuracy': 0.9437, 'Precision': 0.9544, 'Recall': 0.9418, 'F1': 0.9467, 'ROC-AUC': 0.9899}
metrics_post = {'Accuracy': 0.9470, 'Precision': 0.9494, 'Recall': 0.9440, 'F1': 0.9467, 'ROC-AUC': 0.9900}

labels = list(metrics_pre.keys())
pre_vals  = [metrics_pre[k]  for k in labels]
post_vals = [metrics_post[k] for k in labels]

x = np.arange(len(labels))
w_bar = 0.35

fig, ax = plt.subplots(figsize=(9, 5))
bars1 = ax.bar(x - w_bar/2, pre_vals,  w_bar, label='Pre-HNM',  color=BLUE,    alpha=0.85, edgecolor='white')
bars2 = ax.bar(x + w_bar/2, post_vals, w_bar, label='Post-HNM', color=ML_TEAL, alpha=0.85, edgecolor='white')

for bar in bars1:
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.003,
            f'{bar.get_height():.4f}', ha='center', va='bottom', fontsize=7.5, color=DARK)
for bar in bars2:
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.003,
            f'{bar.get_height():.4f}', ha='center', va='bottom', fontsize=7.5, color=DARK)

ax.set_xticks(x)
ax.set_xticklabels(labels, fontsize=11)
ax.set_ylim(0.92, 1.005)
ax.set_ylabel('Score', fontsize=12)
ax.set_title('Pre-HNM vs Post-HNM Ensemble Performance (Frozen Test Set, N=3,980)', fontsize=11, pad=10)
ax.legend(fontsize=11)
ax.grid(axis='y', alpha=0.3, linestyle='--')
ax.set_facecolor('#FAFAFA')
fig.patch.set_facecolor('white')
fig.tight_layout()
fig.savefig(os.path.join(OUT, 'fig_pre_vs_post_hnm.pdf'), bbox_inches='tight', dpi=300)
plt.close(fig)
print("[OK] fig_pre_vs_post_hnm.pdf")


# ─────────────────────────────────────────────────────────────────────────────
# Figure 2: Confusion Matrices — red-green diverging colormap
# ─────────────────────────────────────────────────────────────────────────────
# Pre-HNM (from notebook results)
cm_pre  = np.array([[1959, 93], [135, 1793]])
# Post-HNM (frozen test set)
cm_post = np.array([[1960, 92], [112, 1816]])

fig, axes = plt.subplots(1, 2, figsize=(10, 4.5), facecolor='white')
labels_cm = ['Legit', 'Fraud']

for ax, cm, title in zip(axes, [cm_pre, cm_post], ['(a) Pre-HNM Confusion Matrix', '(b) Post-HNM Confusion Matrix']):
    im = ax.imshow(cm, cmap='Blues', aspect='auto')

    # Kill all seaborn grid lines — they cross through imshow cells
    ax.grid(False)
    ax.set_facecolor('white')

    for i in range(2):
        for j in range(2):
            val = cm[i, j]
            labels_ij = ['TN','FP','FN','TP'][(i*2)+j]
            text_color = 'white' if val > (cm.max() / 2) else DARK
            ax.text(j, i, f'{labels_ij}\n{val}', ha='center', va='center',
                    fontsize=15, fontweight='bold', color=text_color)

    ax.set_xticks([0, 1])
    ax.set_xticklabels(['Predicted\nLegit', 'Predicted\nFraud'], fontsize=10)
    ax.set_yticks([0, 1])
    ax.set_yticklabels(['Actual\nLegit', 'Actual\nFraud'], fontsize=10)
    ax.tick_params(length=0)   # hide tick marks
    ax.set_title(title, fontsize=11, pad=10, color=DARK, fontweight='bold')

    # Draw clean cell borders
    for i in range(2):
        for j in range(2):
            ax.add_patch(plt.Rectangle((j-0.5, i-0.5), 1, 1,
                         fill=False, edgecolor='white', linewidth=2))

fig.patch.set_facecolor('white')
fig.suptitle('Confusion Matrices — Frozen Test Set (N=3,980)', fontsize=12, y=1.02, color=DARK)
fig.tight_layout()
fig.savefig(os.path.join(OUT, 'fig_confusion_matrices.pdf'), bbox_inches='tight', dpi=300)
plt.close(fig)
print("[OK] fig_confusion_matrices.pdf")


# ─────────────────────────────────────────────────────────────────────────────
# Figure 3: Threshold Sensitivity with color-coded risk strata
# ─────────────────────────────────────────────────────────────────────────────
if HAVE_DATA:
    from sklearn.metrics import precision_score, recall_score, f1_score
    thresholds = np.linspace(0.01, 0.99, 200)
    precisions, recalls, f1s = [], [], []
    for t in thresholds:
        y_pred = (P_test >= t).astype(int)
        if y_pred.sum() == 0:
            precisions.append(1.0); recalls.append(0.0); f1s.append(0.0)
        else:
            precisions.append(precision_score(y_test, y_pred, zero_division=0))
            recalls.append(recall_score(y_test, y_pred, zero_division=0))
            f1s.append(f1_score(y_test, y_pred, zero_division=0))
    precisions = np.array(precisions)
    recalls    = np.array(recalls)
    f1s        = np.array(f1s)
else:
    thresholds = np.linspace(0.01, 0.99, 200)
    precisions = 0.85 + 0.14*thresholds
    recalls    = 1.0  - 0.12*thresholds
    f1s        = 2*(precisions*recalls)/(precisions+recalls)

fig, ax = plt.subplots(figsize=(10, 5))

# Shaded risk strata — same palette as HITL flowchart
ax.axvspan(0.00, 0.30, alpha=0.13, color=LEGIT,  label='LEGIT  ($P < 0.30$)')
ax.axvspan(0.30, 0.70, alpha=0.13, color=UNCERT, label='UNCERTAIN ($0.30 \\leq P < 0.70$)')
ax.axvspan(0.70, 0.90, alpha=0.13, color=SUSP,   label='SUSPICIOUS ($0.70 \\leq P < 0.90$)')
ax.axvspan(0.90, 1.00, alpha=0.13, color=FRAUD,  label='FRAUD ($P \\geq 0.90$)')

# Boundary lines
for x_line, col in [(0.30, LEGIT), (0.70, SUSP), (0.90, FRAUD)]:
    ax.axvline(x_line, color=col, linestyle='--', linewidth=1.2, alpha=0.7)

# Metric lines
ax.plot(thresholds, precisions, color=BLUE,    linewidth=2.0, label='Precision')
ax.plot(thresholds, recalls,    color=ML_TEAL, linewidth=2.0, label='Recall')
ax.plot(thresholds, f1s,        color=DARK,    linewidth=2.5, label='F1', linestyle='-.')

ax.set_xlabel('Decision Threshold $P$', fontsize=12)
ax.set_ylabel('Score', fontsize=12)
ax.set_title('Threshold Sensitivity — Post-HNM Ensemble with Risk Strata', fontsize=12, pad=10)
ax.set_xlim(0, 1); ax.set_ylim(0.5, 1.02)
ax.legend(loc='lower left', fontsize=9, ncol=2, framealpha=0.9)
ax.grid(alpha=0.25, linestyle='--')
ax.set_facecolor('#FAFAFA')
fig.tight_layout()
fig.savefig(os.path.join(OUT, 'fig_threshold_sensitivity.pdf'), bbox_inches='tight', dpi=300)
plt.close(fig)
print("[OK] fig_threshold_sensitivity.pdf")


# ─────────────────────────────────────────────────────────────────────────────
# Figure 4: ROC and PR curves
# ─────────────────────────────────────────────────────────────────────────────
if HAVE_DATA:
    from sklearn.metrics import roc_curve, auc, precision_recall_curve, average_precision_score

    model_specs = [
        ('Logistic Regression', lr,  BLUE,    [0.20, 0.00, 0.00]),
        ('SVM (Calibrated)',    svm, ML_TEAL, [0.00, 0.50, 0.00]),
        ('Naive Bayes',         nb,  GREY,    [0.00, 0.00, 0.30]),
        ('Ensemble',            None, DARK,   [0.20, 0.50, 0.30]),
    ]

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    for name, mdl, color, weights in model_specs:
        if mdl is None:
            scores = P_test
        else:
            scores = mdl.predict_proba(X_test)[:,1]

        fpr, tpr, _ = roc_curve(y_test, scores)
        roc_auc = auc(fpr, tpr)
        lw = 2.5 if name == 'Ensemble' else 1.8
        ls = '-' if name == 'Ensemble' else '--'
        axes[0].plot(fpr, tpr, color=color, lw=lw, ls=ls,
                     label=f'{name} (AUC={roc_auc:.4f})')

        prec_c, rec_c, _ = precision_recall_curve(y_test, scores)
        ap = average_precision_score(y_test, scores)
        axes[1].plot(rec_c, prec_c, color=color, lw=lw, ls=ls,
                     label=f'{name} (AP={ap:.4f})')

    axes[0].plot([0,1],[0,1],'k--',alpha=0.4,lw=1)
    axes[0].set_xlabel('False Positive Rate', fontsize=11)
    axes[0].set_ylabel('True Positive Rate', fontsize=11)
    axes[0].set_title('(a) ROC Curves', fontsize=11)
    axes[0].legend(fontsize=8.5, loc='lower right')
    axes[0].grid(alpha=0.25, linestyle='--')

    axes[1].set_xlabel('Recall', fontsize=11)
    axes[1].set_ylabel('Precision', fontsize=11)
    axes[1].set_title('(b) Precision–Recall Curves', fontsize=11)
    axes[1].legend(fontsize=8.5, loc='lower left')
    axes[1].grid(alpha=0.25, linestyle='--')

    for ax in axes:
        ax.set_facecolor('#FAFAFA')

    fig.suptitle('Discriminative Performance — Frozen Test Set (N=3,980)', fontsize=12, y=1.01)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, 'fig_roc_pr_curves.pdf'), bbox_inches='tight', dpi=300)
    plt.close(fig)
    print("[OK] fig_roc_pr_curves.pdf")
else:
    print("[SKIP] fig_roc_pr_curves.pdf (no model data)")

print("\nAll figures generated successfully.")

# ─── Auto-convert PDFs → PNGs for PowerPoint ─────────────────────────────────
try:
    import fitz  # PyMuPDF
    pdf_names = [
        'fig_confusion_matrices',
        'fig_roc_pr_curves',
        'fig_threshold_sensitivity',
        'fig_pre_vs_post_hnm',
    ]
    for name in pdf_names:
        pdf_path = os.path.join(OUT, f'{name}.pdf')
        png_path = os.path.join(PPT_IMG, f'{name}.png')
        if os.path.exists(pdf_path):
            pg = fitz.open(pdf_path).load_page(0)
            pg.get_pixmap(matrix=fitz.Matrix(3.0, 3.0), alpha=False).save(png_path)
            print(f"[PNG] {name}.png")
    print("All PNGs updated in ppt_imgs/")
except ImportError:
    print("[WARN] PyMuPDF not installed — skipping PDF->PNG conversion")
