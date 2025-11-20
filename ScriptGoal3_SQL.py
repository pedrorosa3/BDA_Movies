import mysql.connector
from mysql.connector import errors
from pymongo import MongoClient
import threading
import random
import time
from concurrent.futures import ThreadPoolExecutor

# ============================================================
# PART A — BASE FUNCTIONS (TP-STYLE)
# ============================================================

# ---------------------------
# MySQL connection à la TP
# ---------------------------
def get_conn(user="root", password="<password>", host="localhost",
             port=3306, database="bda_Group11", autocommit=False):

    return mysql.connector.connect(
        user=user,
        password=password,
        host=host,
        port=port,
        database=database,
        autocommit=autocommit
    )

# ---------------------------
# Generic read_value (TP-style)
# ---------------------------
def read_value(conn, pk_col, pk_val, value_col, table="books"):
    cur = conn.cursor()
    cur.execute(f"SELECT {value_col} FROM {table} WHERE {pk_col} = %s", (pk_val,))
    r = cur.fetchone()
    cur.close()
    return r[0] if r else None

# ---------------------------
# MongoDB connection
# ---------------------------
mongo = MongoClient("mongodb+srv://guiti03_db_user:<password>@cluster0.ezv71oa.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")["bda_Group11"]


# ============================================================
# PART B — TEST 1: CONCURRENT READS (SELECT) — TP STYLE
# ============================================================

def do_select(isbn_value):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT book_title FROM books WHERE ISBN = %s", (isbn_value,))
    r = cur.fetchone()
    cur.close()
    conn.close()
    return r

def concurrent_reads(isbns, workers=50):
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(do_select, i) for i in isbns]
        results = [f.result() for f in futures]
    t1 = time.time()
    print(f"[TEST 1] {len(isbns)} SELECTs with {workers} workers took {t1-t0:.3f}s")
    return results


# ============================================================
# PART C — TEST 2: CONCURRENT WRITES (UPDATE COLLISIONS)
# ============================================================

def do_update(isbn):
    conn = get_conn(autocommit=False)
    cur = conn.cursor()
    try:
        cur.execute("UPDATE books SET publisher = %s WHERE ISBN = %s",
                    (f"Updated_{random.randint(1,1000)}", isbn))
        conn.commit()
    except:
        conn.rollback()
    cur.close()
    conn.close()

def concurrent_updates(isbn, workers=20):
    print(f"[TEST 2] Updating the SAME ISBN ({isbn}) with {workers} workers...")
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(do_update, isbn) for _ in range(workers)]
        _ = [f.result() for f in futures]
    print("[TEST 2] Done.\n")


# ============================================================
# PART D — TEST 3: ISOLATION LEVEL TESTS
# ============================================================

# -------------- Dirty Read Test --------------
def dirty_read_test(isbn):
    print("[TEST 3A] Dirty Read Test...")
    
    # Writer (uncommited)
    conn1 = get_conn(autocommit=False)
    cur1 = conn1.cursor()

    # Reader
    conn2 = get_conn()
    cur2 = conn2.cursor()

    try:
        cur1.execute("UPDATE books SET publisher='TEMP_DIRTY' WHERE ISBN = %s", (isbn,))
        
        cur2.execute("SELECT publisher FROM books WHERE ISBN = %s", (isbn,))
        value_before = cur2.fetchone()[0]

        print("Reader saw:", value_before)

    finally:
        conn1.rollback()
        cur1.close()
        cur2.close()


# -------------- Non-repeatable read --------------
def nonrepeatable_read_test(isbn):
    print("[TEST 3B] Non-Repeatable Read Test...")

    conn1 = get_conn()
    conn2 = get_conn(autocommit=True)

    cur1 = conn1.cursor()
    cur2 = conn2.cursor()

    cur1.execute("SELECT publisher FROM books WHERE ISBN = %s", (isbn,))
    before = cur1.fetchone()[0]

    cur2.execute("UPDATE books SET publisher='NRR_TEST' WHERE ISBN = %s", (isbn,))

    cur1.execute("SELECT publisher FROM books WHERE ISBN = %s", (isbn,))
    after = cur1.fetchone()[0]

    print("Before:", before)
    print("After :", after)


# -------------- Phantom read --------------
def phantom_read_test():
    print("[TEST 3C] Phantom Read Test...")

    conn1 = get_conn()
    conn2 = get_conn(autocommit=True)

    cur1 = conn1.cursor()
    cur2 = conn2.cursor()

    cur1.execute("SELECT COUNT(*) FROM books WHERE year_of_publication > 2000")
    before = cur1.fetchone()[0]

    cur2.execute("""
        INSERT INTO books(ISBN, book_title, book_author, year_of_publication, publisher)
        VALUES (%s, 'Phantom', 'P', 2022, 'P')
    """, (random.randint(999000000, 999999999),))

    cur1.execute("SELECT COUNT(*) FROM books WHERE year_of_publication > 2000")
    after = cur1.fetchone()[0]

    print("Before:", before)
    print("After :", after)


# ============================================================
# PART E — TEST 4: FORCED DEADLOCK (TWO WRITERS)
# ============================================================

def deadlock_worker(thread_id, isbn_a, isbn_b):
    conn = get_conn(autocommit=False)
    cur = conn.cursor()

    try:
        cur.execute("UPDATE books SET publisher=%s WHERE ISBN=%s",
                    (f"T{thread_id}_A", isbn_a))

        time.sleep(1)

        cur.execute("UPDATE books SET publisher=%s WHERE ISBN=%s",
                    (f"T{thread_id}_B", isbn_b))

        conn.commit()

    except Exception as e:
        print(f"[DEADLOCK THREAD {thread_id}] ERROR:", e)
        conn.rollback()

    cur.close()
    conn.close()


def deadlock_test():
    print("\n[TEST 4] FORCING DEADLOCK...\n")

    isbn_a = "111111111"
    isbn_b = "222222222"

    conn = get_conn(autocommit=True)
    cur = conn.cursor()
    cur.execute("""
        INSERT IGNORE INTO books (ISBN, book_title, book_author, year_of_publication, publisher)
        VALUES (%s, %s, %s, %s, %s)
    """, (isbn_a, "A", "A", 2000, "P"))

    cur.execute("""
        INSERT IGNORE INTO books (ISBN, book_title, book_author, year_of_publication, publisher)
        VALUES (%s, %s, %s, %s, %s)
    """, (isbn_b, "B", "B", 2001, "P"))
    cur.close()
    conn.close()

    t1 = threading.Thread(target=deadlock_worker, args=(1, isbn_a, isbn_b))
    t2 = threading.Thread(target=deadlock_worker, args=(2, isbn_b, isbn_a))

    t1.start()
    t2.start()

    t1.join()
    t2.join()

    print("[TEST 4] Deadlock test finished.\n")


# ============================================================
# MAIN MENU (RUN ALL TESTS)
# ============================================================

if __name__ == "__main__":
    print("\n========== RUNNING ALL CONCURRENCY TESTS ==========\n")

    # TEST 1
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT ISBN FROM books LIMIT 100")
    sample_isbns = [r[0] for r in cur.fetchall()]
    cur.close()
    conn.close()
    isbns = sample_isbns * 2
    concurrent_reads(isbns, workers=50)

    # TEST 2
    concurrent_updates(sample_isbns[0], workers=20)

    # TEST 3
    dirty_read_test(sample_isbns[1])
    nonrepeatable_read_test(sample_isbns[2])
    phantom_read_test()

    # TEST 4
    deadlock_test()

    print("\n========== ALL TESTS COMPLETE ==========\n")

