import pickle
import pandas as pd
from sklearn.metrics import roc_curve, auc
import matplotlib.pyplot as plt
import seaborn as sns
import joblib

print('Loading models and data...')
split = pickle.load(open('split_indices.pkl', 'rb'))
test_idx = split['test']
df = pd.read_csv('master_dataset.csv')
X_test = df.loc[test_idx, 'text'].fillna('')
y_test = df.loc[test_idx, 'label']

vec = joblib.load('final_vectorizer.pkl')
models = joblib.load('final_models.pkl')

print('Transforming data...')
X_test_vec = vec.transform(X_test)

lr = models['lr']
svm = models['svm']
nb = models['nb']
weights = models.get('weights', (0.5, 0.3, 0.2))
W_LR, W_SVM, W_NB = weights

print('Calculating probabilities...')
p_lr = lr.predict_proba(X_test_vec)[:,1]
p_svm = svm.predict_proba(X_test_vec)[:,1]
p_nb = nb.predict_proba(X_test_vec)[:,1]
p_ens = W_LR * p_lr + W_SVM * p_svm + W_NB * p_nb

print('Calculating ROC metrics...')
fpr_lr, tpr_lr, _ = roc_curve(y_test, p_lr)
auc_lr = auc(fpr_lr, tpr_lr)

fpr_svm, tpr_svm, _ = roc_curve(y_test, p_svm)
auc_svm = auc(fpr_svm, tpr_svm)

fpr_nb, tpr_nb, _ = roc_curve(y_test, p_nb)
auc_nb = auc(fpr_nb, tpr_nb)

fpr_ens, tpr_ens, _ = roc_curve(y_test, p_ens)
auc_ens = auc(fpr_ens, tpr_ens)

print('Plotting...')
sns.set_theme(style='whitegrid')
plt.figure(figsize=(10, 8))

# Plot each base model
plt.plot(fpr_lr, tpr_lr, color='#3498db', lw=2, linestyle='--', label=f'Logistic Regression (AUC = {auc_lr:.4f})')
plt.plot(fpr_svm, tpr_svm, color='#e67e22', lw=2, linestyle='-.', label=f'SVM (Calibrated) (AUC = {auc_svm:.4f})')
plt.plot(fpr_nb, tpr_nb, color='#2ecc71', lw=2, linestyle=':', label=f'Naive Bayes (AUC = {auc_nb:.4f})')

# Plot the ensemble bolder
plt.plot(fpr_ens, tpr_ens, color='#e74c3c', lw=3, label=f'Ensemble (Weighted) (AUC = {auc_ens:.4f})')

# Random guess line
plt.plot([0, 1], [0, 1], color='#7f8c8d', lw=1, linestyle='-', alpha=0.5, label='Random Guess (AUC = 0.5000)')

plt.xlim([-0.01, 1.0])
plt.ylim([0.0, 1.02])
plt.xlabel('False Positive Rate', fontsize=14, fontweight='bold')
plt.ylabel('True Positive Rate', fontsize=14, fontweight='bold')
plt.title('ROC Curves — Test Set', fontsize=16, fontweight='bold', pad=15)
plt.legend(loc='lower right', fontsize=12, frameon=True, shadow=True, borderpad=1)

# Thicker borders like the user's image
ax = plt.gca()
for spine in ax.spines.values():
    spine.set_linewidth(2)
    spine.set_color('black')

plt.tight_layout()
out_file = 'figures/fig_all_roc_comparison.png'
plt.savefig(out_file, dpi=300, bbox_inches='tight')
print(f'Done! Saved to {out_file}')
