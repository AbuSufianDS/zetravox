import pandas as pd
import joblib
import urllib.request
import os
import re
import nltk
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report

nltk.download('stopwords', quiet=True)
from nltk.corpus import stopwords

STOPWORDS = set(stopwords.words('english'))


def clean_text(text):
    text = text.lower()
    text = re.sub(r'[^a-zA-Z\s]', '', text)
    words = text.split()
    words = [w for w in words if w not in STOPWORDS]
    return ' '.join(words)


def download_sms_dataset():
    url = "https://raw.githubusercontent.com/justmarkham/pydata-dc-2016-tutorial/master/sms.tsv"
    filename = "sms_spam.csv"
    if not os.path.exists(filename):
        urllib.request.urlretrieve(url, filename)
    df = pd.read_csv(filename, sep='\t', header=None, names=['label', 'message'])
    df['label'] = df['label'].map({'ham': 'ham', 'spam': 'spam'})
    return df


def download_uci_dataset():
    url = "https://archive.ics.uci.edu/ml/machine-learning-databases/00228/smsspamcollection.zip"
    zip_path = "smsspam.zip"
    if not os.path.exists(zip_path):
        urllib.request.urlretrieve(url, zip_path)
    import zipfile
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall('.')
    df = pd.read_csv('SMSSpamCollection', sep='\t', header=None, names=['label', 'message'])
    df['label'] = df['label'].map({'ham': 'ham', 'spam': 'spam'})
    return df


def load_all_datasets():
    print("Loading datasets...")

    # Dataset 1: SMS Spam Collection (5,574 messages)
    df1 = download_sms_dataset()
    print(f"SMS dataset: {len(df1)} messages")

    # Dataset 2: UCI SMS Spam Collection (same but different source)
    try:
        df2 = download_uci_dataset()
        print(f"UCI dataset: {len(df2)} messages")
        df = pd.concat([df1, df2], ignore_index=True)
    except:
        df = df1
        print("UCI dataset download failed, using only SMS dataset")

    # Add custom ham examples (greetings, casual messages)
    custom_ham = [
        "Hello, how are you?",
        "Good morning everyone",
        "How's your day going?",
        "Nice weather today",
        "What's up?",
        "Hey, how have you been?",
        "Long time no see",
        "Take care",
        "Have a nice day",
        "See you later",
        "Coffee time",
        "Just waking up",
        "Feeling great today",
        "Weekend vibes",
        "Good night",
        "TGIF",
        "Monday blues",
        "Happy Friday",
        "Great weather",
        "Beautiful day",
        "Just finished work",
        "Time to relax",
        "Can't wait for the weekend",
        "Feeling productive",
        "Making progress",
    ]

    custom_df = pd.DataFrame({'label': ['ham'] * len(custom_ham), 'message': custom_ham})
    df = pd.concat([df, custom_df], ignore_index=True)

    print(f"Total combined dataset: {len(df)} messages")
    print(f"Spam: {(df['label'] == 'spam').sum()}, Ham: {(df['label'] == 'ham').sum()}")

    return df


def train_model():
    print("=" * 50)
    print("Training Advanced Spam Detection Model")
    print("=" * 50)

    df = load_all_datasets()
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

    model = LogisticRegression(C=1.0, max_iter=1000, class_weight='balanced')
    model.fit(X_train_vec, y_train)

    y_pred = model.predict(X_test_vec)
    print(f"\nAccuracy: {accuracy_score(y_test, y_pred):.4f}")
    print(classification_report(y_test, y_pred))

    os.makedirs('spam_service/models', exist_ok=True)
    joblib.dump(model, 'spam_service/models/spam_model.pkl')
    joblib.dump(vectorizer, 'spam_service/models/vectorizer.pkl')

    print("\nTesting specific messages:")
    test_messages = [
        "Hello, how are you?",
        "Good morning",
        "Free money click here",
        "Congratulations you won a prize"
    ]
    for msg in test_messages:
        cleaned = clean_text(msg)
        vec = vectorizer.transform([cleaned])
        pred = model.predict(vec)[0]
        prob = model.predict_proba(vec)[0]
        spam_prob = prob[1] if model.classes_[1] == 'spam' else prob[0]
        print(f"  '{msg}' -> {pred.upper()} (confidence: {spam_prob:.3f})")


if __name__ == "__main__":
    train_model()