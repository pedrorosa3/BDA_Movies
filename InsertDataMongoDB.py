from pymongo import MongoClient, UpdateOne
import pandas as pd

# ---- CONFIGURAÇÕES ----
USE_LOCAL_DB = True      # True → usar Mongo local; False → usar Atlas
LIMITED = False          # True → limitar a 20.000 linhas; False → importar tudo

# ---- CONEXÃO AO MONGODB ----
if USE_LOCAL_DB:
    MONGO_USER = "root"
    MONGO_PASS = "<password>"
    MONGO_HOST = "localhost"
    MONGO_PORT = "27017"
    DB_NAME = "bda_Group11"

    LOCAL_URI = f"mongodb://{MONGO_USER}:{MONGO_PASS}@{MONGO_HOST}:{MONGO_PORT}/"
    client = MongoClient(LOCAL_URI)
    db = client[DB_NAME]
    print("Ligação ao MongoDB local estabelecida com sucesso\n")
else:
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
nrows = 20000 if LIMITED else None

users = pd.read_csv(
    "users.csv",
    sep=";",
    encoding="ISO-8859-1",
    on_bad_lines="skip",
    low_memory=False,
    nrows=nrows
)

# Remover duplicados de ID
users = users.drop_duplicates(subset=["User-ID"], keep="first")
if LIMITED:
    print(f"→ {len(users):,} utilizadores únicos (limitado a 20.000).")
else:
    print(f"→ {len(users):,} utilizadores únicos (sem limite).")

users_docs = []
for _, row in users.iterrows():
    doc = {
        "user_id": int(row["User-ID"]),
        "location": str(row["Location"]) if pd.notna(row["Location"]) else None,
        "age": safe_int(row["Age"])
    }
    users_docs.append(doc)

if users_docs:
    batch_size = 5000
    for i in range(0, len(users_docs), batch_size):
        batch = users_docs[i:i + batch_size]
        try:
            db.users.insert_many(batch, ordered=False)
            print(f"   → {i + len(batch):,}/{len(users_docs):,} utilizadores inseridos...")
        except Exception as e:
            print(f"⚠️ Erro no batch {i // batch_size + 1}: {e}")
    print("Users inseridos com sucesso!\n")


# ---- BOOKS ----
print("A carregar books.csv ...")
books = pd.read_csv(
    "books.csv",
    sep=";",
    encoding="ISO-8859-1",
    on_bad_lines="skip",
    low_memory=False,
    nrows=nrows
)
if LIMITED:
    print(f"→ {len(books):,} livros (limitado a 20.000).")
else:
    print(f"→ {len(books):,} livros (sem limite).")

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
        try:
            db.books.insert_many(batch, ordered=False)
            print(f"   → {i + len(batch):,}/{len(books_docs):,} livros inseridos...")
        except Exception as e:
            print(f"⚠️ Erro no batch {i // batch_size + 1}: {e}")
    print("Books inseridos com sucesso!\n")


# ---- RATINGS (embutidos nos livros, com bulk_write) ----
print("A carregar ratings.csv ...")
ratings = pd.read_csv(
    "ratings.csv",
    sep=";",
    encoding="ISO-8859-1",
    on_bad_lines="skip",
    low_memory=False,
    nrows=nrows
)
if LIMITED:
    print(f"→ {len(ratings):,} avaliações (limitado a 20.000).")
else:
    print(f"→ {len(ratings):,} avaliações (sem limite).")

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
print("\nImportação concluída com sucesso!")
