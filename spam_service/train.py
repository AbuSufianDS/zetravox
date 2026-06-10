import pandas as pd
import joblib
import urllib.request
import os
import re
import nltk
from nltk.corpus import stopwords
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.naive_bayes import MultinomialNB, ComplementNB
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import VotingClassifier, RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

nltk.download('stopwords', quiet=True)
STOPWORDS = set(stopwords.words('english'))


def download_dataset():
    url = "https://raw.githubusercontent.com/justmarkham/pydata-dc-2016-tutorial/master/sms.tsv"
    filename = "sms_dataset.csv"
    if not os.path.exists(filename):
        print("Downloading dataset...")
        urllib.request.urlretrieve(url, filename)
    return filename


def clean_text(text):
    text = text.lower()
    text = re.sub(r'[^a-zA-Z\s]', '', text)
    words = text.split()
    words = [w for w in words if w not in STOPWORDS]
    return ' '.join(words)


def train_model():
    print("=" * 50)
    print("Training Improved Spam Detection Model")
    print("=" * 50)

    df = pd.read_csv(download_dataset(), sep='\t', header=None, names=['label', 'message'])
    print(f"Total: {len(df)} (Spam: {(df['label'] == 'spam').sum()}, Ham: {(df['label'] == 'ham').sum()})")

    df['cleaned'] = df['message'].apply(clean_text)

    X_train, X_test, y_train, y_test = train_test_split(
        df['cleaned'], df['label'], test_size=0.2, random_state=42, stratify=df['label']
    )

    vectorizer = TfidfVectorizer(
        max_features=7000,
        ngram_range=(1, 2),
        stop_words='english',
        sublinear_tf=True
    )

    X_train_vec = vectorizer.fit_transform(X_train)
    X_test_vec = vectorizer.transform(X_test)

    clf1 = LogisticRegression(C=1.0, max_iter=1000)
    clf2 = MultinomialNB(alpha=0.5)
    clf3 = ComplementNB(alpha=0.5)

    ensemble = VotingClassifier(
        estimators=[('lr', clf1), ('nb', clf2), ('cnb', clf3)],
        voting='soft'
    )

    ensemble.fit(X_train_vec, y_train)
    y_pred = ensemble.predict(X_test_vec)

    accuracy = accuracy_score(y_test, y_pred)
    print(f"\nAccuracy: {accuracy:.4f}")
    print(classification_report(y_test, y_pred))

    os.makedirs('spam_service/models', exist_ok=True)
    joblib.dump(ensemble, 'spam_service/models/spam_model.pkl')
    joblib.dump(vectorizer, 'spam_service/models/vectorizer.pkl')

    print("\nModel saved! Restart Flask to activate.")
    return ensemble, vectorizer


if __name__ == "__main__":
    train_model()
