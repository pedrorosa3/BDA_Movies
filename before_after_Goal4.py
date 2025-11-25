import mysql.connector
import time

CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "<password>",
    "database": "bda_Group11"
}

# ---------------------------------------------------------
# QUERIES A MEDIR
# ---------------------------------------------------------
QUERIES = {
    "top10_original": """
        SELECT b.book_title, COUNT(*) AS total_ratings
        FROM ratings r
        JOIN books b ON b.ISBN = r.ISBN
        GROUP BY r.ISBN
        ORDER BY total_ratings DESC
        LIMIT 10;
    """
}

# ---------------------------------------------------------
# FUNÇÃO PARA MEDIR TEMPO DE UMA QUERY
# ---------------------------------------------------------
def measure_query(cur, q, runs=3):
    times = []
    for _ in range(runs):
        start = time.perf_counter()
        cur.execute(q)
        cur.fetchall()
        times.append(time.perf_counter() - start)
    return sum(times) / len(times)

# ---------------------------------------------------------
# REMOVER ÍNDICES (estado BEFORE)
# ---------------------------------------------------------
def drop_indexes(cur):
    print("\n--- REMOVING INDEXES (BEFORE) ---")

    indexes = [
        "idx_ratings_isbn",
        "idx_ratings_user",
        "idx_ratings_isbn_user"
    ]

    for idx in indexes:
        try:
            cur.execute(f"ALTER TABLE ratings DROP INDEX {idx};")
            print(f"Removed index {idx}")
        except:
            print(f"Index {idx} does not exist — skipping")

# ---------------------------------------------------------
# CRIAR ÍNDICES (estado AFTER)
# ---------------------------------------------------------
def create_indexes(cur):
    print("\n--- CREATING INDEXES (AFTER) ---")

    commands = [
        "ALTER TABLE ratings ADD INDEX idx_ratings_isbn (ISBN);",
        "ALTER TABLE ratings ADD INDEX idx_ratings_user (user_id);",
        "ALTER TABLE ratings ADD INDEX idx_ratings_isbn_user (ISBN, user_id);"
    ]

    for cmd in commands:
        try:
            cur.execute(cmd)
            print("Created:", cmd)
        except Exception as e:
            print("Error creating index:", e)

# ---------------------------------------------------------
# MAIN PIPELINE
# ---------------------------------------------------------
def main():
    conn = mysql.connector.connect(**CONFIG)
    cur = conn.cursor()

    print("\n========================================")
    print("     AUTOMATIC BEFORE-AFTER TEST")
    print("========================================")

    # ---------------------------
    # DROP INDEXES → BEFORE
    # ---------------------------
    drop_indexes(cur)

    conn.commit()

    print("\n--- MEASURING BEFORE ---")
    before_times = {}
    for name, query in QUERIES.items():
        before_times[name] = measure_query(cur, query)
        print(f"{name}: {before_times[name]:.4f}s")

    # ---------------------------
    # CREATE INDEXES → AFTER
    # ---------------------------
    create_indexes(cur)
    conn.commit()

    print("\n--- MEASURING AFTER ---")
    after_times = {}
    for name, query in QUERIES.items():
        after_times[name] = measure_query(cur, query)
        print(f"{name}: {after_times[name]:.4f}s")

    # ---------------------------
    # SHOW FINAL COMPARISON
    # ---------------------------
    print("\n========================================")
    print("         FINAL BEFORE/AFTER TABLE")
    print("========================================")
    print(f"{'Query':25} | {'BEFORE (s)':12} | {'AFTER (s)':12} | {'IMPROVEMENT'}")
    print("-" * 65)
    for name in QUERIES.keys():
        before = before_times[name]
        after = after_times[name]
        improvement = ((before - after) / before) * 100 if before > 0 else 0
        print(f"{name:25} | {before:12.4f} | {after:12.4f} | {improvement:8.2f}%")

    print("\nDone.\n")

    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
