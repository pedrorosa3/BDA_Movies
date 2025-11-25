#!/usr/bin/env python3
"""
FinalGoal4.py
Master script to run BEFORE/AFTER performance tests and index/schema tuning
for the hybrid MySQL + MongoDB recommendation project.

What it does (fully automated):
 - Connects to MySQL and MongoDB
 - Drops specified indexes (BEFORE)
 - Measures baseline timings for: MySQL top10, Mongo find_one, Mongo aggregation, Hybrid (MySQL top10 -> Mongo lookup)
 - Creates recommended indexes + rebuilds materialized stats (AFTER)
 - Re-measures same operations
 - Outputs a summary table and writes CSV "finalgoal4_results.csv"

IMPORTANT: adjust CONFIG_MYSQL or MONGO_URI if your credentials differ.
"""

import time
import csv
import traceback
from datetime import datetime

# Paths to uploaded files (developer note: using uploaded file paths)
UPLOADED_SCRIPT_PATH = "ScriptGoal3_SQL.py"

# -------------------------
# CONFIG: adapt if needed
# -------------------------
CONFIG_MYSQL = {
    "host": "localhost",
    "user": "root",
    "password": "<password>",
    "database": "bda_Group11",
    "connection_timeout": 10
}

MONGO_URI = "mongodb://root:<password>@localhost:27017/"
#MONGO_URI = "mongodb+srv://pedrorosa3:<password>@cluster0.fw6ylm1.mongodb.net/?appName=Cluster0"

MONGO_DBNAME = "bda_Group11"

# ISBN to test (you provided example "0671870432")
TEST_ISBN_PREFERRED = "0671870432"

# How many runs to average per measured query
MEASURE_RUNS = 3

# --------------------------------------------------------
# Imports that require packages (ensure installed):
# pip install mysql-connector-python pymongo
# --------------------------------------------------------
try:
    import mysql.connector
    from pymongo import MongoClient
except Exception:
    raise RuntimeError("Missing dependencies. Run: pip install mysql-connector-python pymongo")

# --------------------------------------------------------
# Helper measurement utilities
# --------------------------------------------------------
def avg_time(func, runs=MEASURE_RUNS):
    """Measure average runtime of func() over runs (seconds)."""
    times = []
    for _ in range(runs):
        t0 = time.perf_counter()
        func()
        times.append(time.perf_counter() - t0)
    return sum(times) / len(times)

# --------------------------------------------------------
# MySQL operations
# --------------------------------------------------------
class MySQLHelper:
    def __init__(self, cfg):
        self.cfg = cfg
        self.conn = None
        self.cur = None

    def connect(self):
        self.conn = mysql.connector.connect(**self.cfg)
        self.cur = self.conn.cursor(buffered=True)
        # Ensure autocommit for DDL; major operations will commit explicitly
        self.conn.autocommit = True

    def close(self):
        if self.cur:
            self.cur.close()
        if self.conn:
            self.conn.close()

    def drop_indexes_safe(self):
        """
        Try dropping known indexes on ratings.
        If they don't exist, skip.
        This keeps table data intact but removes index structures (BEFORE state).
        """
        indexes = ["idx_ratings_isbn", "idx_ratings_user", "idx_ratings_isbn_user"]
        for idx in indexes:
            try:
                self.cur.execute(f"ALTER TABLE ratings DROP INDEX {idx};")
                print(f"MySQL: dropped index {idx}")
            except mysql.connector.Error as e:
                # index may not exist — skip
                print(f"MySQL: could not drop {idx} (probably doesn't exist): {e.msg}")

    def create_indexes(self):
        """
        Create recommended indexes for ratings table to speed up group-by and lookups.
        """
        commands = [
            "ALTER TABLE ratings ADD INDEX idx_ratings_isbn (ISBN);",
            "ALTER TABLE ratings ADD INDEX idx_ratings_user (user_id);",
            "ALTER TABLE ratings ADD INDEX idx_ratings_isbn_user (ISBN, user_id);",
            # optional: index on book_title in books if searching by title
            "ALTER TABLE books ADD INDEX idx_books_title (book_title(100));"
        ]
        for cmd in commands:
            try:
                self.cur.execute(cmd)
                print(f"MySQL: executed: {cmd}")
            except mysql.connector.Error as e:
                print(f"MySQL: error executing index cmd (may already exist): {e.msg}")

    def create_book_stats_table(self):
        """
        Create (or replace) book_stats table with aggregated values.
        This acts like a materialized view to speed up frequent aggregations.
        """
        try:
            # Drop if exists to refresh fully (safe: recompute)
            self.cur.execute("DROP TABLE IF EXISTS book_stats;")
            # Create table with aggregates
            create_sql = """
                CREATE TABLE book_stats AS
                SELECT ISBN,
                       COUNT(*) AS total_ratings,
                       AVG(book_rating) AS avg_rating
                FROM ratings
                GROUP BY ISBN;
            """
            self.cur.execute(create_sql)
            # Add index on total_ratings for ORDER BY queries
            self.cur.execute("ALTER TABLE book_stats ADD INDEX idx_stats_total (total_ratings);")
            print("MySQL: book_stats table created and indexed.")
        except Exception as e:
            print("MySQL: failed to create book_stats:", e)

    # -------------------------
    # Queries to measure
    # -------------------------
    def query_top10_original(self):
        sql = """
            SELECT b.book_title, COUNT(*) AS total_ratings
            FROM ratings r
            JOIN books b ON b.ISBN = r.ISBN
            GROUP BY r.ISBN
            ORDER BY total_ratings DESC
            LIMIT 10;
        """
        self.cur.execute(sql)
        return self.cur.fetchall()

    def query_top10_stats(self):
        sql = """
            SELECT b.book_title, s.total_ratings
            FROM book_stats s
            JOIN books b ON b.ISBN = s.ISBN
            ORDER BY s.total_ratings DESC
            LIMIT 10;
        """
        try:
            self.cur.execute(sql)
            return self.cur.fetchall()
        except mysql.connector.Error as e:
            # book_stats may not exist yet
            print("MySQL: query_top10_stats failed (book_stats missing?)", e.msg)
            return []

    def get_top_n_isbns(self, n=10):
        sql = """
            SELECT ISBN
            FROM ratings
            GROUP BY ISBN
            ORDER BY COUNT(*) DESC
            LIMIT %s;
        """
        self.cur.execute(sql, (n,))
        rows = self.cur.fetchall()
        return [r[0] for r in rows]

# --------------------------------------------------------
# MongoDB operations
# --------------------------------------------------------
class MongoHelper:
    def __init__(self, uri, dbname):
        self.uri = uri
        self.dbname = dbname
        self.client = None
        self.db = None

    def connect(self):
        self.client = MongoClient(self.uri, maxPoolSize=50)
        self.db = self.client[self.dbname]

    def close(self):
        if self.client:
            self.client.close()

    def drop_indexes(self):
        """
        Drop indexes on users and book_ratings (leaves _id index intact).
        This creates a BEFORE state with minimal indexes.
        """
        try:
            self.db.users.drop_indexes()
            print("Mongo: dropped indexes on users")
        except Exception as e:
            print("Mongo: could not drop indexes on users:", str(e))

        try:
            self.db.book_ratings.drop_indexes()
            print("Mongo: dropped indexes on book_ratings")
        except Exception as e:
            print("Mongo: could not drop indexes on book_ratings:", str(e))

    def create_indexes_and_stats(self):
        """
        Create recommended indexes and rebuild book_stats collection (materialized stats).
        """
        try:
            self.db.users.create_index([("user_id", 1)], unique=True)
            print("Mongo: created index users.user_id")
        except Exception as e:
            print("Mongo: error creating users.user_id index:", e)

        try:
            self.db.book_ratings.create_index([("ISBN", 1)])
            print("Mongo: created index book_ratings.ISBN")
            # multikey index for ratings.user_id if queries need to search inside array
            self.db.book_ratings.create_index([("ratings.user_id", 1)])
            print("Mongo: created multikey index book_ratings.ratings.user_id")
        except Exception as e:
            print("Mongo: error creating book_ratings indexes:", e)

        # Rebuild book_stats collection using aggregation pipeline
        try:
            pipeline = [
                {"$unwind": "$ratings"},
                {"$group": {
                    "_id": "$ISBN",
                    "total": {"$sum": 1},
                    "avg": {"$avg": "$ratings.book_rating"}
                }},
                {"$merge": {"into": "book_stats", "whenMatched": "replace"}}
            ]
            self.db.book_ratings.aggregate(pipeline, allowDiskUse=True)
            self.db.book_stats.create_index([("_id", 1)])
            self.db.book_stats.create_index([("total", -1)])
            print("Mongo: book_stats rebuilt and indexed.")
        except Exception as e:
            print("Mongo: failed to rebuild book_stats:", e)

    # -------------------------
    # Queries to measure
    # -------------------------
    def find_book_ratings(self, isbn):
        """Return the full book_ratings document (may include array 'ratings')."""
        return self.db.book_ratings.find_one({"ISBN": isbn})

    def aggregate_avg_rating(self, isbn):
        pipeline = [
            {"$match": {"ISBN": isbn}},
            {"$unwind": "$ratings"},
            {"$group": {"_id": "$ISBN", "avg": {"$avg": "$ratings.book_rating"}}}
        ]
        return list(self.db.book_ratings.aggregate(pipeline))

    def find_book_stats(self, isbn):
        """Lookup in precomputed book_stats (fast). Note: _id is ISBN in book_stats."""
        return self.db.book_stats.find_one({"_id": isbn})

    def get_any_isbn(self):
        doc = self.db.book_ratings.find_one({}, {"ISBN": 1})
        return doc["ISBN"] if doc and "ISBN" in doc else None

# --------------------------------------------------------
# Hybrid operations (MySQL + Mongo)
# --------------------------------------------------------
class HybridTester:
    def __init__(self, mysql_helper, mongo_helper):
        self.mysql = mysql_helper
        self.mongo = mongo_helper

    def hybrid_lookup_docs(self):
        """MySQL top10 -> for each ISBN fetch full Mongo document."""
        isbns = self.mysql.get_top_n_isbns(10)
        results = []
        for isbn in isbns:
            results.append(self.mongo.find_book_ratings(isbn))
        return results

    def hybrid_lookup_stats(self):
        """MySQL top10 -> for each ISBN fetch Mongo book_stats (precomputed)."""
        isbns = self.mysql.get_top_n_isbns(10)
        results = []
        for isbn in isbns:
            results.append(self.mongo.find_book_stats(isbn))
        return results

# --------------------------------------------------------
# Main automated pipeline
# --------------------------------------------------------
def run_all(test_isbn):
    # Connect
    mysql_h = MySQLHelper(CONFIG_MYSQL)
    mongo_h = MongoHelper(MONGO_URI, MONGO_DBNAME)
    try:
        mysql_h.connect()
        mongo_h.connect()
    except Exception as e:
        print("Failed to connect to databases:", e)
        return

    hybrid = HybridTester(mysql_h, mongo_h)

    # If test_isbn not found in Mongo, try to auto-select one
    try:
        if not mongo_h.find_book_ratings(test_isbn):
            fallback = mongo_h.get_any_isbn()
            if fallback:
                print(f"Preferred ISBN '{test_isbn}' not found in Mongo. Falling back to '{fallback}'.")
                test_isbn = fallback
            else:
                print("No ISBN found in Mongo collection; hybrid tests may be meaningless.")
    except Exception:
        print("Error checking test ISBN in Mongo (continuing).")

    # Prepare containers for results
    results = {
        "mysql_top10_original_before": None,
        "mysql_top10_stats_before": None,
        "mongo_find_ratings_before": None,
        "mongo_aggregate_avg_before": None,
        "hybrid_docs_before": None,
        # after
        "mysql_top10_original_after": None,
        "mysql_top10_stats_after": None,
        "mongo_find_ratings_after": None,
        "mongo_aggregate_avg_after": None,
        "mongo_book_stats_lookup_after": None,
        "hybrid_docs_after": None,
        "hybrid_stats_after": None
    }

    print("\n=== STEP 1: DROP INDEXES (BEFORE state) ===")
    try:
        mysql_h.drop_indexes_safe()
        mongo_h.drop_indexes()
    except Exception as e:
        print("Error while dropping indexes:", e)
        traceback.print_exc()

    # -------------------------
    # BEFORE measurements
    # -------------------------
    print("\n=== STEP 2: MEASURE BEFORE ===")
    try:
        results["mysql_top10_original_before"] = avg_time(mysql_h.query_top10_original)
        print("Measured MySQL top10 original (before):", results["mysql_top10_original_before"])
    except Exception as e:
        print("Error measuring MySQL top10 original (before):", e)

    try:
        results["mongo_find_ratings_before"] = avg_time(lambda: mongo_h.find_book_ratings(test_isbn))
        print("Measured Mongo find_one book_ratings (before):", results["mongo_find_ratings_before"])
    except Exception as e:
        print("Error measuring Mongo find_one (before):", e)

    try:
        results["mongo_aggregate_avg_before"] = avg_time(lambda: mongo_h.aggregate_avg_rating(test_isbn))
        print("Measured Mongo aggregate avg (before):", results["mongo_aggregate_avg_before"])
    except Exception as e:
        print("Error measuring Mongo aggregate (before):", e)

    try:
        results["hybrid_docs_before"] = avg_time(hybrid.hybrid_lookup_docs)
        print("Measured Hybrid (MySQL top10 -> Mongo docs) (before):", results["hybrid_docs_before"])
    except Exception as e:
        print("Error measuring hybrid docs (before):", e)

    # -------------------------
    # APPLY INDEXES and rebuild stats (AFTER)
    # -------------------------
    print("\n=== STEP 3: CREATE INDEXES & REBUILD STATS (AFTER state) ===")
    try:
        mysql_h.create_indexes()
        mysql_h.create_book_stats_table()
    except Exception as e:
        print("Error creating MySQL indexes/book_stats:", e)

    try:
        mongo_h.create_indexes_and_stats()
    except Exception as e:
        print("Error creating Mongo indexes/book_stats:", e)

    # Give DBs a short moment to settle (optional)
    time.sleep(1)

    # -------------------------
    # AFTER measurements
    # -------------------------
    print("\n=== STEP 4: MEASURE AFTER ===")
    try:
        results["mysql_top10_original_after"] = avg_time(mysql_h.query_top10_original)
        print("Measured MySQL top10 original (after):", results["mysql_top10_original_after"])
    except Exception as e:
        print("Error measuring MySQL top10 original (after):", e)

    try:
        results["mysql_top10_stats_after"] = avg_time(mysql_h.query_top10_stats)
        print("Measured MySQL top10 via book_stats (after):", results["mysql_top10_stats_after"])
    except Exception as e:
        print("Error measuring MySQL top10 stats (after):", e)

    try:
        results["mongo_find_ratings_after"] = avg_time(lambda: mongo_h.find_book_ratings(test_isbn))
        print("Measured Mongo find_one book_ratings (after):", results["mongo_find_ratings_after"])
    except Exception as e:
        print("Error measuring Mongo find_one (after):", e)

    try:
        results["mongo_aggregate_avg_after"] = avg_time(lambda: mongo_h.aggregate_avg_rating(test_isbn))
        print("Measured Mongo aggregate avg (after):", results["mongo_aggregate_avg_after"])
    except Exception as e:
        print("Error measuring Mongo aggregate (after):", e)

    try:
        results["mongo_book_stats_lookup_after"] = avg_time(lambda: mongo_h.find_book_stats(test_isbn))
        print("Measured Mongo book_stats lookup (after):", results["mongo_book_stats_lookup_after"])
    except Exception as e:
        print("Error measuring Mongo book_stats lookup (after):", e)

    try:
        results["hybrid_docs_after"] = avg_time(hybrid.hybrid_lookup_docs)
        print("Measured hybrid docs (after):", results["hybrid_docs_after"])
    except Exception as e:
        print("Error measuring hybrid docs (after):", e)

    try:
        results["hybrid_stats_after"] = avg_time(hybrid.hybrid_lookup_stats)
        print("Measured hybrid stats (after):", results["hybrid_stats_after"])
    except Exception as e:
        print("Error measuring hybrid stats (after):", e)

    # -------------------------
    # SUMMARY + CSV EXPORT
    # -------------------------
    print("\n=== STEP 5: SUMMARY TABLE ===\n")
    rows_for_csv = []
    def summarise(name_before, name_after, label):
        b = results.get(name_before)
        a = results.get(name_after)
        if b is None and a is None:
            return
        improvement = None
        if b and a:
            improvement = ((b - a) / b) * 100
        rows_for_csv.append({
            "operation": label,
            "before_s": b if b is not None else "",
            "after_s": a if a is not None else "",
            "improvement_pct": f"{improvement:.2f}%" if improvement is not None else ""
        })

    summarise("mysql_top10_original_before", "mysql_top10_original_after", "MySQL top10 (raw GROUP BY)")
    summarise("mysql_top10_original_before", "mysql_top10_stats_after", "MySQL top10 (via book_stats)")
    summarise("mongo_find_ratings_before", "mongo_find_ratings_after", "Mongo find_one book_ratings")
    summarise("mongo_aggregate_avg_before", "mongo_aggregate_avg_after", "Mongo aggregate avg (unwind)")
    summarise("mongo_aggregate_avg_before", "mongo_book_stats_lookup_after", "Mongo book_stats lookup")
    summarise("hybrid_docs_before", "hybrid_docs_after", "Hybrid: MySQL top10 + Mongo docs")
    summarise("hybrid_docs_before", "hybrid_stats_after", "Hybrid: MySQL top10 + Mongo book_stats")

    # Print table to console
    header = f"{'Operation':45} | {'BEFORE (s)':>12} | {'AFTER (s)':>12} | {'IMPROVEMENT':>12}"
    print(header)
    print("-" * len(header))
    for r in rows_for_csv:
        print(f"{r['operation']:45} | {str(r['before_s']):>12} | {str(r['after_s']):>12} | {r['improvement_pct']:>12}")

    # Write CSV
    csv_name = f"finalgoal4_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    with open(csv_name, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["operation", "before_s", "after_s", "improvement_pct"])
        writer.writeheader()
        for r in rows_for_csv:
            writer.writerow(r)
    print(f"\nResults exported to {csv_name}")

    # Close DBs
    mysql_h.close()
    mongo_h.close()
    print("\nAll done. Close the script and use the CSV/table values in your report.")

# --------------------------------------------------------
# Entrypoint
# --------------------------------------------------------
if __name__ == "__main__":
    print("FinalGoal4 master script starting...")
    print("References to uploaded files (for convenience):")
    print(" - Script used in Goal3:", UPLOADED_SCRIPT_PATH)
    # use preferred ISBN but allow fallback if not present
    run_all(TEST_ISBN_PREFERRED)
