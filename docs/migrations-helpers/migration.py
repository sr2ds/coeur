import os
import sqlite3
import uuid


# Function to update the database and compact it
def update_database(db_file, db_number):
    connection = sqlite3.connect(db_file)
    cursor = connection.cursor()

    # Write-Ahead Log mode to avoid large temporary files
    cursor.execute("PRAGMA journal_mode=WAL")
    connection.commit()

    # 1. Get the current columns of the 'posts' table
    cursor.execute("PRAGMA table_info(posts)")
    columns = cursor.fetchall()

    # 2. Check if the 'id' column exists
    columns_names = [column[1] for column in columns]
    if "id" not in columns_names:
        print(f"Column 'id' not found in {db_file}. Skipping...")
        connection.close()
        return

    # 3. Create the new 'posts' table with the 'uuid', 'db' column, and the other columns
    create_new_table_sql = """
    CREATE TABLE posts_new (
        uuid TEXT PRIMARY KEY NOT NULL,
        title TEXT NOT NULL,
        content TEXT,
        content_format TEXT,
        path TEXT,
        extra TEXT,
        date TEXT,
        image TEXT,
        db INTEGER NOT NULL
    );
    """
    cursor.execute(create_new_table_sql)

    # 4. Copy the data to the new table and generate UUIDs for each row
    cursor.execute("SELECT title, content, content_format, path, extra, date, image FROM posts")
    rows = cursor.fetchall()

    for row in rows:
        new_uuid = str(uuid.uuid4())  # Generate a new UUID for each row
        cursor.execute(
            """
        INSERT INTO posts_new (uuid, title, content, content_format, path, extra, date, image, db)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (new_uuid, row[0], row[1], row[2], row[3], row[4], row[5], row[6], db_number),
        )

    # 5. Delete the old 'posts' table
    cursor.execute("DROP TABLE posts")

    # 6. Rename the new table to 'posts'
    cursor.execute("ALTER TABLE posts_new RENAME TO posts")

    # Commit the changes
    connection.commit()

    # 7. Compact the database to remove fragmentation (outside of the transaction)
    connection.close()  # Close the connection before compacting
    with sqlite3.connect(db_file) as conn:
        conn.execute("VACUUM")  # Compact the database outside the transaction


# Function to iterate over all files in the db/ directory
def process_all_databases():
    db_dir = "db/"

    # Iterate over all files in the db/ directory
    for db_number, filename in enumerate(sorted(os.listdir(db_dir)), start=1):
        if filename.endswith(".sqlite"):
            db_file = os.path.join(db_dir, filename)
            print(f"Updating database: {db_file} (Database {db_number})")

            # Update the database
            update_database(db_file, db_number)


# Run the script
process_all_databases()
