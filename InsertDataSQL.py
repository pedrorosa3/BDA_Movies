import mysql.connector
import pandas as pd

# ---------- CONEXÃO À BASE DE DADOS ----------
mydb = mysql.connector.connect(
    host="localhost",
    user="root",
    password="<password>",
    database="bda_Group11"
)
cursor = mydb.cursor()


try:
    cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")  # desativar FK temporariamente
    cursor.execute("TRUNCATE TABLE ratings;")
    cursor.execute("TRUNCATE TABLE books;")
    cursor.execute("TRUNCATE TABLE users;")
    cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")  # reativar FK
    mydb.commit()
    print("Tabelas limpas com sucesso!\n")
except Exception as e:
    print("Erro ao limpar tabelas:", e)
    exit()


def insert_in_batches(cursor, sql, data, batch_size=5000):
    """Executa INSERTs em blocos para evitar erros"""
    total = len(data)
    for i in range(0, total, batch_size):
        batch = data[i:i + batch_size]
        cursor.executemany(sql, batch)
        mydb.commit()
        print(f"   → {i + len(batch):,}/{total:,} inseridos...")


print("A carregar users.csv ...")

users = pd.read_csv("users.csv", sep=';', encoding="ISO-8859-1", on_bad_lines='skip', low_memory=False)
print(f"→ {len(users):,} utilizadores encontrados.")

users_data = [
    (
        int(row["User-ID"]), #Converte o id do user para inteiro
        str(row["Location"]) if pd.notna(row["Location"]) else None, #Se nao tiver vazio, converte a location para string
        int(row["Age"]) if pd.notna(row["Age"]) else None #Converte a idade do user para inteiro
    )
    for _, row in users.iterrows()
]

sql_users = """
    INSERT IGNORE INTO users (user_id, location, age)
    VALUES (%s, %s, %s)
"""
insert_in_batches(cursor, sql_users, users_data, batch_size=5000)
print("Users inseridos com sucesso!")



print("\nA carregar books.csv ...")

books = pd.read_csv("books.csv", sep=';', encoding="ISO-8859-1", on_bad_lines='skip', low_memory=False)
print(f"→ {len(books):,} livros encontrados.")

def safe_int(value):
    try:
        return int(value)
    except (ValueError, TypeError):
        return None

books_data = [
    (
        str(row["ISBN"]),
        str(row["Book-Title"]),
        str(row["Book-Author"]),
        safe_int(row["Year-Of-Publication"]), #Nem todos os anos de publicacao sao convertiveis, por isso temos de ter esta funcao para nao parar a execucao caso dê erro.
        str(row["Publisher"]),
        str(row["Image-URL-S"]),
        str(row["Image-URL-M"]),
        str(row["Image-URL-L"])
    )
    for _, row in books.iterrows()
]

sql_books = """
    INSERT IGNORE INTO books
    (ISBN, book_title, book_author, year_of_publication, publisher,
     image_url_s, image_url_m, image_url_l)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
"""
insert_in_batches(cursor, sql_books, books_data, batch_size=5000)
print("Books inseridos com sucesso!")



print("\nA carregar ratings.csv ...")

ratings = pd.read_csv("ratings.csv", sep=';', encoding="ISO-8859-1", on_bad_lines='skip', low_memory=False)
print(f"→ {len(ratings):,} avaliações encontradas.")

ratings_data = [
    (
        int(row["User-ID"]),
        str(row["ISBN"]),
        int(row["Book-Rating"]) if pd.notna(row["Book-Rating"]) else None
    )
    for _, row in ratings.iterrows()
]

sql_ratings = """
    INSERT IGNORE INTO ratings (user_id, ISBN, book_rating)
    VALUES (%s, %s, %s)
"""
insert_in_batches(cursor, sql_ratings, ratings_data, batch_size=5000)
print("Ratings inseridos com sucesso!")


cursor.close()
mydb.close()
print("\nImportação concluída com sucesso!")



