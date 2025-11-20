import mysql.connector
from pymongo import MongoClient
import threading
import random
import time
from concurrent.futures import ThreadPoolExecutor

# ============================================================
# BASE
# ============================================================

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

mongo = MongoClient(
    "mongodb+srv://guiti03_db_user:<password>@cluster0.ezv71oa.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
)["bda_Group11"]

# ============================================================
# METRICS / SUMMARY STATE
# ============================================================

METRICS = {
    "test1_time": None,
    "test2_time": None,
    "test3A_time": None,
    "test3B_time": None,
    "test4_time": None,
    "test5_time": None,
    "test6_time": None,
    "test7_time": None,
    "lost_update_errors": 0,
    "lost_update_no_row": 0,
    "deadlocks": 0,
    "dirty_read_observed": False,
    "nonrepeatable_observed": False,
    "phantom_observed": False,
    "total_runtime": None,
}


# ============================================================
# TEST 1 — CONCURRENT READS (SELECT em BOOKS)
# ============================================================

def do_select(isbn_value):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT book_title FROM books WHERE ISBN=%s", (isbn_value,))
    r = cur.fetchone()
    cur.close()
    conn.close()
    return r

def concurrent_reads(isbns, workers=50):
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(do_select, i) for i in isbns]
        _ = [f.result() for f in futures]
    elapsed = time.time()-t0
    METRICS["test1_time"] = elapsed
    print(f"[TEST 1] {len(isbns)} SELECTs in {elapsed:.3f}s")


# ============================================================
# TEST 2 — CONCURRENT WRITES (UPDATE collisions)
# ============================================================

def do_update(isbn):
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE books SET publisher=%s WHERE ISBN=%s",
            (f"Updated_{random.randint(1,999)}", isbn)
        )
        conn.commit()
    except:
        conn.rollback()
    cur.close()
    conn.close()

def concurrent_updates(isbn, workers=20):
    print(f"[TEST 2] Updating ISBN {isbn} with {workers} workers...")
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(do_update, isbn) for _ in range(workers)]
        _ = [f.result() for f in futures]
    elapsed = time.time()-t0
    METRICS["test2_time"] = elapsed
    print(f"[TEST 2] Done in {elapsed:.3f}s\n")


# ============================================================
# TEST 3A — LOST UPDATE (UNSAFE — BASED ON YOUR CODE)
# ============================================================

def unsafe_increment(isbn, user_id, delay_before_write=0.5):
    conn = get_conn()
    cur = conn.cursor()
    try:
        conn.start_transaction()

        # 1) READ without exclusive lock
        cur.execute("""
            SELECT book_rating FROM ratings
            WHERE ISBN = %s AND user_id = %s
            FOR SHARE
        """, (isbn, user_id))

        row = cur.fetchone()
        if not row:
            conn.rollback()
            METRICS["lost_update_no_row"] += 1
            return "no-row"

        current = row[0]

        # simulate "thinking"
        time.sleep(delay_before_write)

        new_value = current + 1

        # 2) WRITE (unsafe — no version check)
        cur.execute("""
            UPDATE ratings SET book_rating = %s
            WHERE ISBN = %s AND user_id = %s
        """, (new_value, isbn, user_id))

        conn.commit()
        return ("ok", current, new_value)

    except Exception as e:
        conn.rollback()
        METRICS["lost_update_errors"] += 1
        return ("err", str(e))

    finally:
        cur.close()
        conn.close()


def run_unsafe_lost_update_test(isbn, user_id):
    print("\n[TEST 3A] LOST UPDATE (UNSAFE VERSION)\n")

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=2) as ex:
        f1 = ex.submit(unsafe_increment, isbn, user_id, 1.0)
        f2 = ex.submit(unsafe_increment, isbn, user_id, 0.2)
        r1 = f1.result()
        r2 = f2.result()

    METRICS["test3A_time"] = time.time() - t0

    print("Thread 1:", r1)
    print("Thread 2:", r2)

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT book_rating FROM ratings
        WHERE ISBN = %s AND user_id = %s
    """, (isbn, user_id))
    final = cur.fetchone()[0]
    cur.close()
    conn.close()

    print("Final value:", final, "\n")


# ============================================================
# TEST 3B — FIXED VERSION (SELECT ... FOR UPDATE)
# ============================================================

def safe_increment_for_update(isbn, user_id, delay=0.5):
    conn = get_conn()
    cur = conn.cursor()
    try:
        conn.start_transaction()

        # 1) READ with exclusive lock
        cur.execute("""
            SELECT book_rating FROM ratings
            WHERE ISBN = %s AND user_id = %s
            FOR UPDATE
        """, (isbn, user_id))

        row = cur.fetchone()
        if not row:
            conn.rollback()
            return "no-row"

        current = row[0]
        time.sleep(delay)

        new_value = current + 1

        # 2) WRITE (safe)
        cur.execute("""
            UPDATE ratings SET book_rating = %s
            WHERE ISBN=%s AND user_id=%s
        """, (new_value, isbn, user_id))

        conn.commit()
        return ("ok", current, new_value)

    except Exception as e:
        conn.rollback()
        return ("err", str(e))

    finally:
        cur.close()
        conn.close()


def run_safe_for_update_test(isbn, user_id):
    print("\n[TEST 3B] PREVENT LOST UPDATE (FOR UPDATE)\n")

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=2) as ex:
        f1 = ex.submit(safe_increment_for_update, isbn, user_id, 1.0)
        f2 = ex.submit(safe_increment_for_update, isbn, user_id, 0.2)

        r1 = f1.result()
        r2 = f2.result()

    METRICS["test3B_time"] = time.time() - t0

    print("Thread 1:", r1)
    print("Thread 2:", r2)

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT book_rating FROM ratings
        WHERE ISBN=%s AND user_id=%s
    """, (isbn, user_id))
    final = cur.fetchone()[0]
    cur.close()
    conn.close()

    print("Final value:", final, "\n")


# ============================================================
# TEST 4 — ISOLATION LEVEL EFFECTS (REPEATABLE READ vs READ COMMITTED)
# ============================================================

def txn_a_isolation(isbn):
    conn = get_conn()
    cur = conn.cursor()

    # Set isolation level
    cur.execute("SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ")
    conn.start_transaction()

    # First read
    cur.execute("SELECT publisher FROM books WHERE ISBN=%s", (isbn,))
    v1 = cur.fetchone()[0]
    print("[TEST 4A - A] First read:", v1)

    time.sleep(2.0)  # Let B update

    # Second read
    cur.execute("SELECT publisher FROM books WHERE ISBN=%s", (isbn,))
    v2 = cur.fetchone()[0]
    print("[TEST 4A - A] Second read:", v2)

    conn.commit()
    cur.close()
    conn.close()


def txn_b_isolation(isbn):
    time.sleep(0.5)  # Wait for A's first read

    conn = get_conn()
    cur = conn.cursor()

    conn.start_transaction()
    cur.execute("UPDATE books SET publisher = %s WHERE ISBN=%s",
                (f"ISO_{random.randint(1,999)}", isbn))
    conn.commit()

    print("[TEST 4A - B] Updated and committed")
    cur.close()
    conn.close()


def isolation_level_test(isbn):
    print("\n[TEST 4] Isolation Level Effects (Repeatable Read Test)\n")

    t0 = time.time()
    t1 = threading.Thread(target=txn_a_isolation, args=(isbn,))
    t2 = threading.Thread(target=txn_b_isolation, args=(isbn,))

    t1.start()
    t2.start()

    t1.join()
    t2.join()

    METRICS["test4_time"] = time.time() - t0

    print("[TEST 4] Done.\n")


# ============================================================
# TEST 5 — ISOLATION ANOMALIES
# ============================================================

def dirty_read_test(isbn):
    print("[TEST 5A] Dirty Read")
    conn1 = get_conn(autocommit=False)
    cur1 = conn1.cursor()

    conn2 = get_conn()
    cur2 = conn2.cursor()

    cur1.execute("UPDATE books SET publisher='TEMP' WHERE ISBN=%s", (isbn,))
    cur2.execute("SELECT publisher FROM books WHERE ISBN=%s", (isbn,))
    val = cur2.fetchone()[0]

    print("Reader saw:", val)

    # Este teste é construído para mostrar dirty read
    METRICS["dirty_read_observed"] = True

    conn1.rollback()
    cur1.close(); cur2.close()
    conn2.close()


def nonrepeatable_read_test(isbn):
    print("[TEST 5B] Non-Repeatable Read")

    conn1 = get_conn()
    conn2 = get_conn(autocommit=True)

    cur1 = conn1.cursor()
    cur2 = conn2.cursor()

    cur1.execute("SELECT publisher FROM books WHERE ISBN=%s", (isbn,))
    before = cur1.fetchone()[0]

    cur2.execute("UPDATE books SET publisher='NRR' WHERE ISBN=%s", (isbn,))

    cur1.execute("SELECT publisher FROM books WHERE ISBN=%s", (isbn,))
    after = cur1.fetchone()[0]

    print("Before:", before, "After:", after)

    if before != after:
        METRICS["nonrepeatable_observed"] = True

    cur1.close(); cur2.close()
    conn1.close(); conn2.close()


def phantom_read_test():
    print("[TEST 5C] Phantom Read")

    conn1 = get_conn()
    conn2 = get_conn(autocommit=True)

    cur1 = conn1.cursor()
    cur2 = conn2.cursor()

    cur1.execute("SELECT COUNT(*) FROM books WHERE year_of_publication > 2000")
    before = cur1.fetchone()[0]

    cur2.execute(
        """
        INSERT INTO books(ISBN, book_title, book_author, year_of_publication, publisher)
        VALUES (%s, 'Phantom', 'P', 2023, 'Pub')
        """,
        (random.randint(500000000, 599999999),)
    )

    cur1.execute("SELECT COUNT(*) FROM books WHERE year_of_publication > 2000")
    after = cur1.fetchone()[0]

    print("Before:", before, "After:", after)

    if before != after:
        METRICS["phantom_observed"] = True

    cur1.close(); cur2.close()
    conn1.close(); conn2.close()


# ============================================================
# TEST 6 — FORCED DEADLOCK
# ============================================================

def deadlock_worker(tid, isbn_a, isbn_b):
    conn = get_conn(autocommit=False)
    cur = conn.cursor()
    try:
        cur.execute("UPDATE books SET publisher=%s WHERE ISBN=%s",
                    (f"T{tid}_A", isbn_a))
        time.sleep(1)
        cur.execute("UPDATE books SET publisher=%s WHERE ISBN=%s",
                    (f"T{tid}_B", isbn_b))
        conn.commit()
    except Exception as e:
        print(f"[THREAD {tid}] ERROR:", e)
        METRICS["deadlocks"] += 1
        conn.rollback()
    cur.close(); conn.close()


def deadlock_test():
    print("\n[TEST 6] Forced Deadlock")

    t0 = time.time()

    isbn_a = "111111111"
    isbn_b = "222222222"

    conn = get_conn(autocommit=True)
    cur = conn.cursor()
    cur.execute("""
        INSERT IGNORE INTO books
        (ISBN, book_title, book_author, year_of_publication, publisher)
        VALUES (%s, %s, %s, %s, %s)
    """, (isbn_a, "A", "A", 2000, "P"))

    cur.execute("""
        INSERT IGNORE INTO books
        (ISBN, book_title, book_author, year_of_publication, publisher)
        VALUES (%s, %s, %s, %s, %s)
    """, (isbn_b, "B", "B", 2001, "P"))
    cur.close(); conn.close()

    t1 = threading.Thread(target=deadlock_worker, args=(1, isbn_a, isbn_b))
    t2 = threading.Thread(target=deadlock_worker, args=(2, isbn_b, isbn_a))

    t1.start(); t2.start()
    t1.join(); t2.join()

    METRICS["test6_time"] = time.time() - t0

    print("[TEST 6] Deadlock Finished.\n")


# ============================================================
# TEST 7 — Mixed MySQL + MongoDB Concurrency
# ============================================================

def mysql_insert_books(i):
    conn = get_conn(autocommit=True)
    cur = conn.cursor()
    for _ in range(10):
        cur.execute(
            """
            INSERT IGNORE INTO books(ISBN, book_title, book_author, year_of_publication, publisher)
            VALUES (%s,'X','Y',2000,'P')
            """,
            (random.randint(600000000,699999999),)
        )
    cur.close(); conn.close()


def mysql_read_books(i):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM books")
    cur.fetchall()
    cur.close(); conn.close()


def mongo_update(i):
    mongo.users.update_one(
        {"user_id": random.randint(1,5000)},
        {"$set": {"age": random.randint(10,80)}},
        upsert=True
    )


def mongo_read(i):
    mongo.users.find_one({"user_id": random.randint(1,5000)})


def mixed_concurrency_test():
    print("[TEST 7] Mixed SQL + Mongo concurrency")

    t0 = time.time()
    threads=[]

    for i in range(5):
        threads.append(threading.Thread(target=mysql_insert_books, args=(i,)))
    for i in range(5):
        threads.append(threading.Thread(target=mysql_read_books, args=(i,)))
    for i in range(5):
        threads.append(threading.Thread(target=mongo_update, args=(i,)))
    for i in range(5):
        threads.append(threading.Thread(target=mongo_read, args=(i,)))

    for t in threads: t.start()
    for t in threads: t.join()

    METRICS["test7_time"] = time.time() - t0

    print("[TEST 7] Done.\n")


# ============================================================
# SUMMARY / REPORT
# ============================================================

def print_summary():
    print("\n==================== CONCURRENCY SUMMARY ====================")
    print(f"Test 1  - Concurrent SELECTs time:      {METRICS['test1_time']:.3f}s" if METRICS['test1_time'] else "Test 1  - skipped")
    print(f"Test 2  - Concurrent UPDATEs time:      {METRICS['test2_time']:.3f}s" if METRICS['test2_time'] else "Test 2  - skipped")
    print(f"Test 3A - Lost Update (unsafe):        {METRICS['test3A_time']:.3f}s, errors={METRICS['lost_update_errors']}, no-row={METRICS['lost_update_no_row']}" if METRICS['test3A_time'] else "Test 3A - skipped")
    print(f"Test 3B - FOR UPDATE (safe):           {METRICS['test3B_time']:.3f}s" if METRICS['test3B_time'] else "Test 3B - skipped")
    print(f"Test 4  - Isolation Level test:        {METRICS['test4_time']:.3f}s" if METRICS['test4_time'] else "Test 4  - skipped")
    print(f"Test 5  - Anomalies (dirty/NRR/phantom): time={METRICS['test5_time']:.3f}s" if METRICS['test5_time'] else "Test 5  - partial/implicit time")
    print(f"   Dirty read observed:                {METRICS['dirty_read_observed']}")
    print(f"   Non-repeatable read observed:       {METRICS['nonrepeatable_observed']}")
    print(f"   Phantom read observed:              {METRICS['phantom_observed']}")
    print(f"Test 6  - Forced deadlock time:        {METRICS['test6_time']:.3f}s, deadlocks={METRICS['deadlocks']}" if METRICS['test6_time'] else "Test 6  - skipped")
    print(f"Test 7  - Mixed SQL+Mongo time:        {METRICS['test7_time']:.3f}s" if METRICS['test7_time'] else "Test 7  - skipped")
    print(f"Total runtime (script):                {METRICS['total_runtime']:.3f}s" if METRICS['total_runtime'] else "")
    print("=============================================================\n")


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    print("\n========== RUNNING CONCURRENCY TESTS ==========\n")

    global_t0 = time.time()

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT ISBN FROM books LIMIT 5")
    sample_isbns = [r[0] for r in cur.fetchall()]
    cur.close(); conn.close()

    # TEST 1
    if sample_isbns:
        concurrent_reads(sample_isbns * 2)
    else:
        print("TEST 1 skipped\n")

    # TEST 2
    if sample_isbns:
        concurrent_updates(sample_isbns[0])
    else:
        print("TEST 2 skipped\n")

    # TEST 3 (FOR UPDATE)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT user_id, ISBN FROM ratings LIMIT 1")
    row = cur.fetchone()
    cur.close()
    conn.close()

    if row:
        user_id, isbn_rating = row

        # Teste 3A — Lost Update
        run_unsafe_lost_update_test(isbn_rating, user_id)

        # Teste 3B — Safe Update
        run_safe_for_update_test(isbn_rating, user_id)
    else:
        print("[TEST 3] Skipped (no ratings)\n")

    # TEST 4 — Isolation Level Effects
    if sample_isbns:
        isolation_level_test(sample_isbns[0])
    else:
        print("[TEST 4] Skipped (no books)\n")

    # TEST 5 (Dirty, NRR, Phantom)
    t5_0 = time.time()
    if len(sample_isbns)>=3:
        dirty_read_test(sample_isbns[0])
        nonrepeatable_read_test(sample_isbns[1])
    phantom_read_test()
    METRICS["test5_time"] = time.time() - t5_0

    # TEST 6 (Deadlock)
    deadlock_test()

    # TEST 7 (Mixed SQL+Mongo)
    mixed_concurrency_test()

    METRICS["total_runtime"] = time.time() - global_t0

    print_summary()

    print("============ DONE ============\n")





