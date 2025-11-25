import mysql.connector
from pymongo import MongoClient
import threading
import random
import time
import pandas as pd

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



## PONTO 1 - ÍNDICES PARA LEITURAS MAIS RÁPIDAS


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




## PONTO 2- BATCHING PARA INSERÇÕES

# exemplo de batch mais optimizado



def safe_int(v):
    try:
        return int(v)
    except:
        return None
    
def insert_otimizado():
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cur = conn.cursor()

    # ============================================================
    # BOOKS
    # ============================================================
    print("\n--- Inserir BOOKS ---")

    books = pd.read_csv(
        "books.csv",
        sep=";",
        encoding="ISO-8859-1",
        on_bad_lines="skip",
        low_memory=False
    )

    # Normalizar ISBN e eliminar duplicados
    books["ISBN"] = books["ISBN"].astype(str).str.upper()
    books = books.drop_duplicates(subset=["ISBN"])

    # Limpar tabela
    cur.execute("DELETE FROM books;")
    conn.commit()

    insert_books = """
        INSERT INTO books
        (ISBN, book_title, book_author, year_of_publication, publisher,
         image_url_s, image_url_m, image_url_l)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
    """
    buffer = []
    BATCH_SIZE = 3000

    for _, row in books.iterrows():

        buffer.append((
            row["ISBN"],
            row["Book-Title"] if pd.notna(row["Book-Title"]) else None,
            row["Book-Author"] if pd.notna(row["Book-Author"]) else None,
            safe_int(row["Year-Of-Publication"]),
            row["Publisher"] if pd.notna(row["Publisher"]) else None,
            row["Image-URL-S"] if pd.notna(row["Image-URL-S"]) else None,
            row["Image-URL-M"] if pd.notna(row["Image-URL-M"]) else None,
            row["Image-URL-L"] if pd.notna(row["Image-URL-L"]) else None,
        ))

        if len(buffer) >= BATCH_SIZE:
            cur.executemany(insert_books, buffer)
            conn.commit()
            total += len(buffer)
            buffer.clear()

    # commit final
    if buffer:
        cur.executemany(insert_books, buffer)
        conn.commit()
        total += len(buffer)

    print(f"✔ Total livros inseridos: {total:,}\n")


## PONTO 3- MEDIÇÃO DE TEMPOS SCRIPT SQL

def measure(cur, query, params=None):
    start = time.perf_counter()
    cur.execute(query, params)
    cur.fetchall()
    return time.perf_counter() - start

def teste1():
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cur = conn.cursor()
    commands = [
        "ALTER TABLE ratings ADD INDEX idx_ratings_isbn (ISBN);",
        "ALTER TABLE ratings ADD INDEX idx_ratings_user (user_id);",
        "ALTER TABLE ratings ADD INDEX idx_ratings_isbn_user (ISBN, user_id);",
        "CREATE TABLE IF NOT EXISTS book_stats AS SELECT ISBN, COUNT(*) AS total_ratings,AVG(book_rating) AS avg_rating FROM ratings GROUP BY ISBN;",
        "ALTER TABLE book_stats ADD INDEX idx_stats_total (total_ratings);"
    ]

    for cmd in commands:
        try:
            cur.execute(cmd)
            print("Created:", cmd)
        except Exception as e:
            print("Error creating index:", e)

    queries = [
        ("top10_original", """
            SELECT b.book_title, COUNT(*) AS total_ratings
            FROM ratings r
            JOIN books b ON b.ISBN = r.ISBN
            GROUP BY r.ISBN
            LIMIT 10;
        """),
        ("top10_stats", """
            SELECT b.book_title, s.total_ratings
            FROM book_stats s
            JOIN books b ON b.ISBN = s.ISBN
            ORDER BY s.total_ratings DESC
            LIMIT 10;
        """)
    ]

    for name, q in queries:
        t = measure(cur, q)
        print(f"{name}: {t:.4f}s")

    cur.close()
    conn.close()

teste1()


## PONTO 3 - MEDIÇÃO DE TEMPOS SCRIPT MONGO

def measure(fn):
    t0 = time.perf_counter()
    fn()
    return time.perf_counter() - t0

def get_book(isbn="0671870432"):
    
    return mongo.book_ratings.find_one({"ISBN": isbn})

def get_book_stats(isbn="0671870432"):
    return mongo.book_stats.find_one({"_id": isbn})

print("Ratings array lookup:", measure(lambda: get_book()))
print("Book stats lookup:", measure(lambda: get_book_stats()))


## PONTO 4- Beneficts and tradeoffs of hybrid database systems


'''
Benefícios:

MySQL garante integridade e joins rápidos para dados estruturados.

MongoDB permite armazenar listas grandes e flexíveis (ratings), com inserções rápidas.

Podem usar coleções agregadas para acelerar recomendações.

Trade-offs:

Precisam de manter coerência entre sistemas.

Mais complexidade operacional.

Duplicação de dados (ex.: book_stats em Mongo + MySQL se quiserem).

'''