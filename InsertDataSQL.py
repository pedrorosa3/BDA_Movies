import mysql.connector
import pandas as pd
from config import Config


def safe_int(v):
    try:
        return int(v)
    except:
        return None


def main():
    conn = mysql.connector.connect(
        host=Config.MYSQL_HOST,
        user=Config.MYSQL_USER,
        password=Config.MYSQL_PASSWORD,
        database=Config.MYSQL_DB
    )
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

    batch_size = 2000
    buffer = []
    total = 0

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

        if len(buffer) >= batch_size:
            cur.executemany(insert_books, buffer)
            conn.commit()
            total += len(buffer)
            print(f"   → {total:,} livros inseridos...")
            buffer = []

    if buffer:
        cur.executemany(insert_books, buffer)
        conn.commit()
        total += len(buffer)

    print(f"✔ Total livros inseridos: {total:,}\n")

    # ============================================================
    # RATINGS
    # ============================================================
    print("--- Inserir RATINGS ---")

    ratings = pd.read_csv(
        "ratings.csv",
        sep=";",
        encoding="ISO-8859-1",
        on_bad_lines="skip",
        low_memory=False
    )

    ratings["ISBN"] = ratings["ISBN"].astype(str).str.upper()

    cur.execute("DELETE FROM ratings;")
    conn.commit()

    insert_ratings = """
        INSERT IGNORE INTO ratings (user_id, ISBN, book_rating)
        VALUES (%s,%s,%s)
    """

    batch_size = 4000
    buffer = []
    total = 0

    for _, row in ratings.iterrows():
        buffer.append((
            safe_int(row["User-ID"]),
            row["ISBN"],
            safe_int(row["Book-Rating"])
        ))

        if len(buffer) >= batch_size:
            cur.executemany(insert_ratings, buffer)
            conn.commit()
            total += len(buffer)
            print(f"   → {total:,} ratings inseridos...")
            buffer = []

    if buffer:
        cur.executemany(insert_ratings, buffer)
        conn.commit()
        total += len(buffer)

    print(f"✔ Total ratings inseridos: {total:,}\n")

    cur.close()
    conn.close()
    print("Importação SQL concluída com sucesso!\n")


if __name__ == "__main__":
    main()
