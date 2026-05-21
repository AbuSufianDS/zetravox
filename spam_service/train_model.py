import pandas as pd
import numpy as np
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Embedding, LSTM, Dense, Dropout
from tensorflow.keras.preprocessing.text import Tokenizer
from tensorflow.keras.preprocessing.sequence import pad_sequences
from sklearn.model_selection import train_test_split
import pickle
import os
import urllib.request


def train():
    print("=" * 50)
    print("Training Spam Detection Model")
    print("=" * 50)
    url = "https://raw.githubusercontent.com/justmarkham/pydata-dc-2016-tutorial/master/sms.tsv"
    filename = "sms_dataset.csv"

    if not os.path.exists(filename):
        print("Downloading dataset...")
        urllib.request.urlretrieve(url, filename)
    df = pd.read_csv(filename, sep='\t', header=None, names=['label', 'message'])
    print(f"Loaded {len(df)} messages ({sum(df['label'] == 'spam')} spam, {sum(df['label'] == 'ham')} ham)")
    df['label_num'] = df['label'].map({'ham': 0, 'spam': 1})
    tokenizer = Tokenizer(num_words=10000, oov_token='<OOV>')
    tokenizer.fit_on_texts(df['message'])
    sequences = tokenizer.texts_to_sequences(df['message'])
    max_length = 100
    X = pad_sequences(sequences, maxlen=max_length, padding='post')
    y = df['label_num'].values
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    model = Sequential([
        Embedding(10000, 128, input_length=max_length),
        LSTM(64, dropout=0.2, recurrent_dropout=0.2),
        Dense(32, activation='relu'),
        Dropout(0.5),
        Dense(1, activation='sigmoid')
    ])

    model.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy'])
    print("\nTraining model...")
    model.fit(X_train, y_train, epochs=10, batch_size=32, validation_data=(X_test, y_test), verbose=1)
    loss, accuracy = model.evaluate(X_test, y_test)
    print(f"\n Model accuracy: {accuracy:.4f}")
    os.makedirs('spam_service/models', exist_ok=True)
    model.save('spam_service/models/spam_model.h5')
    with open('spam_service/models/tokenizer.pkl', 'wb') as f:
        pickle.dump(tokenizer, f)

    print("\n Model saved to: spam_service/models/spam_model.h5")
    print(" Tokenizer saved to: spam_service/models/tokenizer.pkl")
    print("\n Spam detection is ready! Restart your app.")


if __name__ == "__main__":
    train()