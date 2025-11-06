from pymongo import MongoClient, UpdateOne
import pandas as pd

# ---- CONEXÃO AO MONGODB ATLAS ----
ATLAS_URI = "mongodb+srv://diogosfb91_db_user:<password>@cluster0.hszfcsx.mongodb.net/?appName=Cluster0"
client = MongoClient(ATLAS_URI)
db = client["bda_Group11"]
print("Ligação ao MongoDB Atlas estabelecida com sucesso\n")


def safe_int(value):
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


# ---- USERS ----
print("A carregar users.csv ...")
users = pd.read_csv(
    "users.csv",
    sep=";",
    encoding="ISO-8859-1",
    on_bad_lines="skip",
    low_memory=False,
    nrows=20000
)

# Remover duplicados de ID
users = users.drop_duplicates(subset=["User-ID"], keep="first")
print(f"→ {len(users):,} utilizadores únicos (limitado a 20.000).")

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


# ---- BOOKS ----
print("A carregar books.csv ...")
books = pd.read_csv(
    "books.csv",
    sep=";",
    encoding="ISO-8859-1",
    on_bad_lines="skip",
    low_memory=False,
    nrows=20000
)
print(f"→ {len(books):,} livros (limitado a 20.000).")

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
        "ratings": []  # Campo inicial vazio
    }
    books_docs.append(doc)

if books_docs:
    batch_size = 5000
    for i in range(0, len(books_docs), batch_size):
        batch = books_docs[i:i + batch_size]
        db.books.insert_many(batch)
        print(f"   → {i + len(batch):,}/{len(books_docs):,} livros inseridos...")
    print("Books inseridos com sucesso!\n")


# ---- RATINGS (embutidos nos livros, com bulk_write) ----
print("A carregar ratings.csv ...")
ratings = pd.read_csv(
    "ratings.csv",
    sep=";",
    encoding="ISO-8859-1",
    on_bad_lines="skip",
    low_memory=False,
    nrows=20000
)
print(f"→ {len(ratings):,} avaliações (limitado a 20.000).")

batch_size = 500
ops = []
count = 0

for _, row in ratings.iterrows():
    user_id = safe_int(row["User-ID"])
    isbn = str(row["ISBN"])
    rating = safe_int(row["Book-Rating"])

    if user_id is not None and isbn:
        ops.append(UpdateOne(
            {"ISBN": isbn},
            {"$push": {"ratings": {"user_id": user_id, "book_rating": rating}}}
        ))

        if len(ops) >= batch_size:
            db.books.bulk_write(ops)
            count += len(ops)
            print(f"   → {count:,}/{len(ratings):,} ratings processados...")
            ops = []

# Inserir o resto
if ops:
    db.books.bulk_write(ops)
    count += len(ops)

print(f"Total de ratings embutidos: {count:,}\n")

# ---- RESUMO ----
print("Resumo final:")
print(f" Users: {db.users.count_documents({}):,}")
print(f" Books: {db.books.count_documents({}):,}")

client.close()
print("\nImportação concluída com sucesso no MongoDB Atlas!")
