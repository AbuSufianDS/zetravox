import sqlite3


def add_columns():
    conn = sqlite3.connect('app.db')
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(user)")
    existing_columns = [col[1] for col in cursor.fetchall()]

    new_columns = [
        ('cover_pic', 'VARCHAR(200)', 'default_cover.jpg'),
        ('relationship_status', 'VARCHAR(50)', None),
        ('work', 'VARCHAR(100)', None),
        ('education', 'VARCHAR(100)', None),
        ('location', 'VARCHAR(100)', None),
        ('website', 'VARCHAR(200)', None),
        ('birthday', 'VARCHAR(20)', None),
        ('gender', 'VARCHAR(20)', None),
        ('interested_in', 'VARCHAR(100)', None),
        ('phone', 'VARCHAR(20)', None),
    ]

    for col_name, col_type, default_value in new_columns:
        if col_name not in existing_columns:
            try:
                if default_value:
                    cursor.execute(f'ALTER TABLE user ADD COLUMN {col_name} {col_type} DEFAULT "{default_value}"')
                else:
                    cursor.execute(f'ALTER TABLE user ADD COLUMN {col_name} {col_type}')
                print(f"Added column: {col_name}")
            except Exception as e:
                print(f"Error adding {col_name}: {e}")
        else:
            print(f"Column already exists: {col_name}")

    conn.commit()
    conn.close()
    print("All columns added successfully!")


if __name__ == '__main__':
    add_columns()