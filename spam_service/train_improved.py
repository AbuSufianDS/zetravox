import pandas as pd
import joblib
import urllib.request
import os
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report


def download_dataset():
    url = "https://raw.githubusercontent.com/justmarkham/pydata-dc-2016-tutorial/master/sms.tsv"
    filename = "sms_dataset.csv"

    if not os.path.exists(filename):
        print(" Downloading dataset...")
        urllib.request.urlretrieve(url, filename)
        print(" Download complete!")
    return filename


def create_custom_data():
    normal_messages = [
        ("Coffee Time", "ham"),
        ("Good morning", "ham"),
        ("Hello everyone", "ham"),
        ("How are you?", "ham"),
        ("Great day today", "ham"),
        ("Feeling happy", "ham"),
        ("Just chilling", "ham"),
        ("Weekend vibes", "ham"),
        ("Lunch time", "ham"),
        ("Break time", "ham"),
        ("On my way", "ham"),
        ("See you later", "ham"),
        ("Take care", "ham"),
        ("Have a nice day", "ham"),
        ("Beautiful weather", "ham"),

        ("Just finished my workout", "ham"),
        ("Coffee is life", "ham"),
        ("Working from home today", "ham"),
        ("Movie night", "ham"),
        ("Dinner time", "ham"),
        ("Good night everyone", "ham"),
        ("TGIF", "ham"),
        ("Monday blues", "ham"),
        ("Feeling productive", "ham"),

        ("Just read a great book, highly recommend it", "ham"),
        ("Looking forward to the weekend", "ham"),
        ("Anyone watching the game tonight?", "ham"),
        ("Need recommendations for a good restaurant", "ham"),

        ("Click here to see my photos", "ham"),
        ("Check out my new profile picture", "ham"),
        ("Follow me for more updates", "ham"),
    ]
    return pd.DataFrame(normal_messages, columns=['message', 'label'])


def clean_text(text):
    text = text.lower()
    text = re.sub(r'[^a-zA-Z\s]', '', text)
    text = ' '.join(text.split())
    return text


def train_improved_model():

    dataset_file = download_dataset()
    df_original = pd.read_csv(dataset_file, sep='\t', header=None, names=['label', 'message'])
    print(f"\n Original dataset: {len(df_original)} messages")

    df_custom = create_custom_data()
    print(f" Added custom messages: {len(df_custom)} messages")

    df = pd.concat([df_original, df_custom], ignore_index=True)
    print(f" Total dataset: {len(df)} messages")

    spam_count = (df['label'] == 'spam').sum()
    ham_count = (df['label'] == 'ham').sum()
    print(f"\n Class balance:")
    print(f"   Spam: {spam_count} ({spam_count / len(df) * 100:.1f}%)")
    print(f"   Ham: {ham_count} ({ham_count / len(df) * 100:.1f}%)")

    print("\n Cleaning messages...")
    df['cleaned'] = df['message'].apply(clean_text)

    X_train, X_test, y_train, y_test = train_test_split(
        df['cleaned'], df['label'], test_size=0.2, random_state=42, stratify=df['label']
    )
    print(" Creating text features...")
    vectorizer = TfidfVectorizer(
        max_features=7000,
        ngram_range=(1, 2),
        stop_words='english',
        min_df=2,
        max_df=0.95
    )

    X_train_vectorized = vectorizer.fit_transform(X_train)
    X_test_vectorized = vectorizer.transform(X_test)
    from sklearn.naive_bayes import ComplementNB
    classifier = ComplementNB()
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
    print("\n Testing on short messages (should NOT be spam):")
    test_messages = [
        "Coffee Time",
        "Good morning",
        "Hello",
        "How are you",
        "Great day",
        "Just chilling",
        "Weekend",
        "Lunch break",
    ]

    for msg in test_messages:
        cleaned = clean_text(msg)
        vectorized = vectorizer.transform([cleaned])
        pred = classifier.predict(vectorized)[0]
        prob = classifier.predict_proba(vectorized)[0]
        confidence = max(prob)

        status = " SPAM (False Positive!)" if pred == "spam" else "HAM"
        color = "\033[91m" if pred == "spam" else "\033[92m"
        print(f"   {color}{status}\033[0m: '{msg}' (confidence: {confidence:.2f})")

    print("\n" + "=" * 60)
    print(" Training complete! Restart your Flask app.")
    print("=" * 60)

    return classifier, vectorizer


if __name__ == "__main__":
    train_improved_model()