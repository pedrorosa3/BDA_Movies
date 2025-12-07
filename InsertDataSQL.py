"""
Grupo 11
Diogo Sousa - 60250; 
Francisco Lopes - 60252;  
Guilherme Almeida - 60264;
Pedro Rosa  - 60294
"""
import mysql.connector
import pandas as pd
from config import Config



# ============================================================
# Função utilitária: converte valores para INT de forma segura
# ============================================================
def safe_int(v):
    """Converte para inteiro; devolve None caso não seja possível."""
    try:
        return int(v)
    except:
        return None


# ============================================================
# PROGRAMA PRINCIPAL
# ============================================================
def main():
    conn = mysql.connector.connect(
        host=Config.MYSQL_HOST,
        user=Config.MYSQL_USER,
        password=Config.MYSQL_PASSWORD,
        database=Config.MYSQL_DB
    )
    cur = conn.cursor()

    # ============================================================
    # 2) IMPORTAR BOOKS
    # ============================================================
    print("--- Inserir BOOKS ---")

    # ------------------------------------------------------------
    # Ler CSV de livros
    # ------------------------------------------------------------
    books = pd.read_csv(
        "books.csv",
        sep=";",                 # separador do dataset original
        encoding="ISO-8859-1",   # codificação original do dataset
        on_bad_lines="skip",     # ignora linhas corrompidas
        low_memory=False         # evita warnings de tipos mistos
    )

    # ------------------------------------------------------------
    # Normalizar ISBN e eliminar duplicados
    # ------------------------------------------------------------
    books["ISBN"] = books["ISBN"].astype(str).str.upper()  # uniformizar ISBN
    books = books.drop_duplicates(subset=["ISBN"])          # evitar duplicados

    # ------------------------------------------------------------
    # Limpar tabela para evitar duplicação de dados
    # ------------------------------------------------------------
    cur.execute("DELETE FROM books;")
    conn.commit()

    # Query preparada para inserção
    insert_books = """
        INSERT INTO books
        (ISBN, book_title, book_author, year_of_publication, publisher,
         image_url_s, image_url_m, image_url_l)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
    """

    batch_size = 2000   # inserir em blocos para grande performance
    buffer = []         # lista temporária
    total = 0           # contador de registos inseridos

    # ------------------------------------------------------------
    # Inserção em batches
    # ------------------------------------------------------------
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

        # Quando buffer atinge o tamanho ideal → inserir no MySQL
        if len(buffer) >= batch_size:
            cur.executemany(insert_books, buffer)
            conn.commit()
            total += len(buffer)
            print(f"   → {total:,} livros inseridos...")
            buffer = []  # limpar buffer

    # Inserir o que sobra no buffer
    if buffer:
        cur.executemany(insert_books, buffer)
        conn.commit()
        total += len(buffer)

    print(f"✔ Total livros inseridos: {total:,}\n")

    # ============================================================
    # 3) IMPORTAR RATINGS
    # ============================================================
    print("--- Inserir RATINGS ---")

    ratings = pd.read_csv(
        "ratings.csv",
        sep=";",               
        encoding="ISO-8859-1",
        on_bad_lines="skip",
        low_memory=False
    )

    ratings["ISBN"] = ratings["ISBN"].astype(str).str.upper()  # normalizar

    # Limpar tabela ratings antes de inserir
    cur.execute("DELETE FROM ratings;")
    conn.commit()

    # Query preparada
    insert_ratings = """
        INSERT IGNORE INTO ratings (user_id, ISBN, book_rating)
        VALUES (%s,%s,%s)
    """

    batch_size = 4000
    buffer = []
    total = 0

    # Inserção em batches
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

    # Inserir últimas linhas
    if buffer:
        cur.executemany(insert_ratings, buffer)
        conn.commit()
        total += len(buffer)

    print(f"✔ Total ratings inseridos: {total:,}\n")

    # ============================================================
    # FECHAR LIGAÇÃO
    # ============================================================
    cur.close()
    conn.close()
    print("Importação SQL concluída com sucesso!\n")


# ============================================================
# EXECUÇÃO DO SCRIPT
# ============================================================
if __name__ == "__main__":
    main()
