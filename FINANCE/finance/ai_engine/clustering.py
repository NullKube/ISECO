# ai_engine/clustering.py
"""
SPENDING PATTERN CLUSTERING
NEW: Real K-means clustering (PRD compliant)
Falls back to simple bucketing if sklearn unavailable
"""

def _expense_to_dict(expense):
    return {
        "id": expense.id,
        "amount": expense.amount,
        "category": getattr(expense, "category", None),
        "date": expense.date.strftime("%Y-%m-%d") if hasattr(expense, "date") else None,
        "user_id": expense.user_id
    }

def cluster_spending_ml(expenses=None, user=None):
    from expenses.models import Expense
    # Get expenses
    if user is not None and expenses is None:
        expenses = Expense.objects.filter(user=user, type="expense")
    elif expenses is None:
        expenses = Expense.objects.filter(type="expense")
    expenses_list = list(expenses)
    if len(expenses_list) < 10:
        return cluster_spending(expenses, user)
    try:
        from sklearn.cluster import KMeans
        import numpy as np
        # Feature engineering: [amount, day_of_month, is_weekend]
        X = []
        for exp in expenses_list:
            features = [
                float(exp.amount),
                exp.date.day,
                1 if exp.date.weekday() >= 5 else 0  # Weekend flag
            ]
            X.append(features)
        X = np.array(X)
        # Normalize features
        from sklearn.preprocessing import StandardScaler
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        # K-Means clustering (3 clusters)
        kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
        labels = kmeans.fit_predict(X_scaled)
        # Group expenses by cluster
        clusters = {"Cluster_0": [], "Cluster_1": [], "Cluster_2": []}
        for idx, label in enumerate(labels):
            clusters[f"Cluster_{label}"].append(expenses_list[idx])
        # Analyze clusters
        cluster_analysis = {}
        for cluster_name, cluster_expenses in clusters.items():
            if not cluster_expenses:
                continue
            avg_amount = sum(float(e.amount) for e in cluster_expenses) / len(cluster_expenses)
            total = sum(float(e.amount) for e in cluster_expenses)
            if avg_amount > 3000:
                cluster_type = "High-Value"
                insight = "Large purchases - plan these carefully"
            elif avg_amount > 1000:
                cluster_type = "Medium-Value"
                insight = "Regular moderate expenses"
            else:
                cluster_type = "Small-Value"
                insight = "Frequent small transactions - potential to optimize"
            cluster_analysis[cluster_name] = {
                "type": cluster_type,
                "count": len(cluster_expenses),
                "total_amount": round(total, 2),
                "avg_amount": round(avg_amount, 2),
                "insight": insight,
                "expenses": [_expense_to_dict(exp) for exp in cluster_expenses[:5]]  # Fix: Convert to dict
            }
        return {
            "method": "k_means",
            "clusters": cluster_analysis
        }
    except ImportError:
        return cluster_spending(expenses, user)
    except Exception as e:
        return cluster_spending(expenses, user)

def cluster_spending(expenses=None, user=None):
    if user is not None and expenses is None:
        from expenses.models import Expense
        expenses = Expense.objects.filter(user=user, type="expense")
    elif expenses is None:
        from expenses.models import Expense
        expenses = Expense.objects.filter(type="expense")
    buckets = {
        "High": [],
        "Medium": [],
        "Low": []
    }
    for exp in expenses:
        if exp.amount >= 5000:
            buckets["High"].append(exp)
        elif exp.amount >= 1000:
            buckets["Medium"].append(exp)
        else:
            buckets["Low"].append(exp)
    # Fix: Convert all Expense objects in buckets to dicts
    buckets = {k: [_expense_to_dict(exp) for exp in v] for k, v in buckets.items()}
    return {
        "method": "simple_bucketing",
        "clusters": buckets
    }
