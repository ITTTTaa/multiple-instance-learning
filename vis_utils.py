
import numpy as np
from sklearn.metrics import roc_curve
import matplotlib.pyplot as plt


def plot_roc(test_label, p_vals):
    test_label = np.asarray(test_label)
    p_vals = np.asarray(p_vals).squeeze()
    fpr, tpr, _ = roc_curve(test_label, p_vals)
    plt.figure()
    plt.plot(fpr, tpr, 'k--', label='ROC curve')
    plt.xlim([0.0, 1.0])
    plt.ylim([0.0, 1.05])
    plt.xlabel('False Positive Rate')
    plt.ylabel('True Positive Rate')
    plt.title('Receiver operating characteristic example')
    plt.legend(loc="lower right")
    plt.show()
