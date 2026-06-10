from app import create_app, db
from app.models import User, Post, Comment, Notification, Message, Task

app = create_app()

import gc
gc.collect()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
