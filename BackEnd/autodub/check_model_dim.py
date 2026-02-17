import pickle
import os
model_path = os.path.abspath("models/gender/gender_lgbm.pkl")
if os.path.exists(model_path):
    with open(model_path, 'rb') as f:
        model = pickle.load(f)
    print(f"Number of features in model: {model.n_features_in_}")
else:
    print("Model not found.")
