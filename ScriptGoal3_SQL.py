import mysql.connector
from pymongo import MongoClient
import threading
import random
import time

# =============================================
# CONFIG
# =============================================
MYSQL_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "<password>",
    "database": "bda_Group11",
}

mongo = MongoClient("mongodb://root:<password>@localhost:27017/")["bda_Group11"]

# =============================================
# MYSQL — WRITER (INSERT INTO BOOKS)
# =============================================
def mysql_insert_books(thread_id):
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cur = conn.cursor()

    start = time.time()
    
    for i in range(30):
        isbn = str(random.randint(100000000, 999999999))
        title = f"Book_{thread_id}_{i}"
        author = "Concurrent Author"
        year = random.randint(1950, 2024)
        publisher = "TestPub"

        try:
            cur.execute("""
                INSERT IGNORE INTO books
                (ISBN, book_title, book_author, year_of_publication, publisher)
                VALUES (%s, %s, %s, %s, %s)
            """, (isbn, title, author, year, publisher))
            conn.commit()
        except Exception as e:
            print(f"[MySQL INSERT Thread {thread_id}] ERROR:", e)

    print(f"[MySQL INSERT Thread {thread_id}] Done in {time.time()-start:.3f}s")
    cur.close()
    conn.close()

# =============================================
# MYSQL — READER (SELECT)
# =============================================
def mysql_read_recommendations(thread_id):
    conn = mysql.connector.connect(
        **MYSQL_CONFIG,
        connection_timeout=5
    )
    cur = conn.cursor(dictionary=True)

    start = time.time()

    for _ in range(5):  # reduzir de 30 para 5
        try:
            cur.execute("""
                SELECT b.book_title, COUNT(*) AS total_ratings
                FROM ratings r FORCE INDEX(idx_ratings_isbn)
                JOIN books b ON b.ISBN = r.ISBN
                GROUP BY r.ISBN
                ORDER BY total_ratings DESC
                LIMIT 10;
            """)
            cur.fetchall()
        except Exception as e:
            print(f"[MySQL READ Thread {thread_id}] ERROR:", e)
            break   # prevenir bloqueio

    print(f"[MySQL READ Thread {thread_id}] Done in {time.time()-start:.3f}s")
    cur.close()
    conn.close()


# =============================================
# MONGO — WRITER (UPSERT USER)
# =============================================
def mongo_update_users(thread_id):
    start = time.time()

    for i in range(40):
        user_id = random.randint(10000, 20000)
        new_location = random.choice(["USA", "Portugal", "Brazil", "UK", None])
        new_age = random.randint(10, 80)

        try:
            mongo.users.update_one(
                {"user_id": user_id},
                {"$set": {"location": new_location, "age": new_age}},
                upsert=True
            )
        except Exception as e:
            print(f"[Mongo UPDATE Thread {thread_id}] ERROR:", e)

    print(f"[Mongo UPDATE Thread {thread_id}] Done in {time.time()-start:.3f}s")

# =============================================
# MONGO — READER (READ USERS)
# =============================================
def mongo_read_users(thread_id):
    start = time.time()

    for _ in range(40):
        rand_id = random.randint(1, 5000)
        try:
            _ = mongo.users.find_one({"user_id": rand_id})
        except Exception as e:
            print(f"[Mongo READ Thread {thread_id}] ERROR:", e)

    print(f"[Mongo READ Thread {thread_id}] Done in {time.time()-start:.3f}s")

# =============================================
# RUN EVERYTHING CONCURRENTLY
# =============================================
def run_concurrency_test():

    threads = []

    # MYSQL writers
    for i in range(5):
        t = threading.Thread(target=mysql_insert_books, args=(i,))
        threads.append(t)

    # MYSQL readers
    for i in range(5):
        t = threading.Thread(target=mysql_read_recommendations, args=(i,))
        threads.append(t)

    # Mongo writers
    for i in range(5):
        t = threading.Thread(target=mongo_update_users, args=(i,))
        threads.append(t)

    # Mongo readers
    for i in range(5):
        t = threading.Thread(target=mongo_read_users, args=(i,))
        threads.append(t)

    # START ALL
    print("\n🚀 Starting full concurrency test (MySQL + Mongo, Reads + Writes)...\n")
    start_global = time.time()

    for t in threads:
        t.start()

    for t in threads:
        t.join()

    print(f"\n ALL THREADS FINISHED in {time.time()-start_global:.3f}s")

# =============================================
# MAIN
# =============================================
if __name__ == "__main__":
    run_concurrency_test()
