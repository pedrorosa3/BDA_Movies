from pymongo import MongoClient
import pandas as pd


# CONEXÃO AO MONGODB ATLAS
ATLAS_URI = "mongodb+srv://guiti03_db_user:<password>@cluster0.ezv71oa.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"

client = MongoClient(ATLAS_URI)
db = client["bda_Group11"]
print("Ligação ao MongoDB Atlas estabelecida com sucesso\n")


def safe_int(value):
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


print("A carregar users.csv ...")

users = pd.read_csv("users.csv", sep=";", encoding="ISO-8859-1", on_bad_lines="skip", low_memory=False)
print(f"→ {len(users):,} utilizadores encontrados.")

users_docs = []
for _, row in users.iterrows():
    doc = {
        "user_id": int(row["User-ID"]),
        "location": str(row["Location"]) if pd.notna(row["Location"]) else None,
        "age": safe_int(row["Age"])
    }
    users_docs.append(doc)

if users_docs:
    db.users.insert_many(users_docs)
    print("Users inseridos com sucesso!\n")


print("A carregar books.csv ...")

books = pd.read_csv("books.csv", sep=";", encoding="ISO-8859-1", on_bad_lines="skip", low_memory=False)
print(f"→ {len(books):,} livros encontrados.")

books_docs = []
for _, row in books.iterrows():
    doc = {
        "ISBN": str(row["ISBN"]),
        "book_title": str(row["Book-Title"]) if pd.notna(row["Book-Title"]) else None,
        "book_author": str(row["Book-Author"]) if pd.notna(row["Book-Author"]) else None,
        "year_of_publication": safe_int(row["Year-Of-Publication"]),
        "publisher": str(row["Publisher"]) if pd.notna(row["Publisher"]) else None,
        "image_url_s": str(row["Image-URL-S"]) if pd.notna(row["Image-URL-S"]) else None,
        "image_url_m": str(row["Image-URL-M"]) if pd.notna(row["Image-URL-M"]) else None,
        "image_url_l": str(row["Image-URL-L"]) if pd.notna(row["Image-URL-L"]) else None,
    }
    books_docs.append(doc)

if books_docs:
    # Inserir em blocos (para evitar excesso de dados)
    batch_size = 5000
    for i in range(0, len(books_docs), batch_size):
        batch = books_docs[i:i + batch_size]
        db.books.insert_many(batch)
        print(f"   → {i + len(batch):,}/{len(books_docs):,} livros inseridos...")
    print("Books inseridos com sucesso!\n")


print("A carregar ratings.csv ...")

ratings = pd.read_csv("ratings.csv", sep=";", encoding="ISO-8859-1", on_bad_lines="skip", low_memory=False)
print(f"→ {len(ratings):,} avaliações encontradas.")

ratings_docs = []
for _, row in ratings.iterrows():
    doc = {
        "user_id": int(row["User-ID"]),
        "ISBN": str(row["ISBN"]),
        "book_rating": safe_int(row["Book-Rating"])
    }
    ratings_docs.append(doc)

if ratings_docs:
    batch_size = 10000
    for i in range(0, len(ratings_docs), batch_size):
        batch = ratings_docs[i:i + batch_size]
        db.ratings.insert_many(batch)
        print(f"   → {i + len(batch):,}/{len(ratings_docs):,} avaliações inseridas...")
    print("Ratings inseridos com sucesso!\n")


print("Resumo final:")
print(f" Users: {db.users.count_documents({}):,}")
print(f" Books: {db.books.count_documents({}):,}")
print(f" Ratings: {db.ratings.count_documents({}):,}")

client.close()
print("\n Importação concluída com sucesso no MongoDB Atlas!")
