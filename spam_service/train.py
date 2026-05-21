import pandas as pd
import joblib
import urllib.request
import os
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report


def download_dataset():
    url = "https://raw.githubusercontent.com/justmarkham/pydata-dc-2016-tutorial/master/sms.tsv"
    filename = "sms_dataset.csv"

    if not os.path.exists(filename):
        print(" Downloading training dataset...")
        urllib.request.urlretrieve(url, filename)
        print(" Download complete!")
    return filename


def clean_text(text):
    text = text.lower()
    text = re.sub(r'[^a-zA-Z\s]', '', text)
    text = ' '.join(text.split())
    return text


def train_model():
    dataset_file = download_dataset()
    df = pd.read_csv(dataset_file, sep='\t', header=None, names=['label', 'message'])

    print(f"\n Dataset loaded:")
    print(f"   Total messages: {len(df)}")
    print(f"   Spam: {(df['label'] == 'spam').sum()} messages")
    print(f"   Ham: {(df['label'] == 'ham').sum()} messages")
    print("\n Cleaning messages...")
    df['cleaned'] = df['message'].apply(clean_text)
    X_train, X_test, y_train, y_test = train_test_split(
        df['cleaned'], df['label'], test_size=0.2, random_state=42
    )
    print(" Creating text features...")
    vectorizer = TfidfVectorizer(
        max_features=5000,
        ngram_range=(1, 2),
        stop_words='english'
    )

    X_train_vectorized = vectorizer.fit_transform(X_train)
    X_test_vectorized = vectorizer.transform(X_test)
    print(" Training classifier...")
    classifier = MultinomialNB()
    classifier.fit(X_train_vectorized, y_train)
    y_pred = classifier.predict(X_test_vectorized)
    accuracy = accuracy_score(y_test, y_pred)

    print(f"\n Model Performance:")
    print(f"   Accuracy: {accuracy:.4f}")
    print(f"\n{classification_report(y_test, y_pred)}")
    os.makedirs('spam_service/models', exist_ok=True)
    joblib.dump(classifier, 'spam_service/models/spam_model.pkl')
    joblib.dump(vectorizer, 'spam_service/models/vectorizer.pkl')

    print("\n Model saved to:")
    print("   - spam_service/models/spam_model.pkl")
    print("   - spam_service/models/vectorizer.pkl")
    print("\n Testing on sample messages:")
    test_messages = [
        "Free money!!! Click here to win $1000",
        "Hello, how are you doing today?",
        "CONGRATULATIONS! You've won a free iPhone",
        "Meeting at 3pm tomorrow?",
        "Buy cheap viagra online now",
        "Thanks for the meeting yesterday"
    ]

    for msg in test_messages:
        cleaned = clean_text(msg)
        vectorized = vectorizer.transform([cleaned])
        pred = classifier.predict(vectorized)[0]
        prob = classifier.predict_proba(vectorized)[0]
        confidence = max(prob)
        status = " SPAM" if pred == "spam" else " HAM"
        print(f"   {status}: '{msg[:40]}' (confidence: {confidence:.2f})")

    print("\n Training complete!")
    print(" Spam detection is ready. Restart your Flask app.")

    return classifier, vectorizer


if __name__ == "__main__":
    train_model()