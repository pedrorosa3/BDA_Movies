from pymongo import MongoClient
import pandas as pd
from collections import defaultdict

# =====================================================================
# CONFIG
# =====================================================================
USE_LOCAL_DB = False      # True → conectar local; False → Atlas
LIMITED = True         # True → 20.000 primeiras linhas

# =====================================================================
# CONEXÃO AO MONGO
# =====================================================================
if USE_LOCAL_DB:
    MONGO_USER = "root"
    MONGO_PASS = "<password>"
    MONGO_HOST = "localhost"
    MONGO_PORT = "27017"
    DB_NAME = "bda_Group11"

    URI = f"mongodb://{MONGO_USER}:{MONGO_PASS}@{MONGO_HOST}:{MONGO_PORT}/"
    client = MongoClient(URI)
else:
    ATLAS_URI = "mongodb+srv://guiti03_db_user:<password>@cluster0.ezv71oa.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
    client = MongoClient(ATLAS_URI)
    DB_NAME = "bda_Group11"

db = client[DB_NAME]
print("Ligação ao MongoDB estabelecida.\n")

# =====================================================================
# DELETE COLEÇÕES ANTIGAS
# =====================================================================
for col in ["users", "book_ratings"]:
    if col in db.list_collection_names():
        db[col].drop()
print("Coleções antigas removidas.\n")


# =====================================================================
# AUXILIAR
# =====================================================================
def safe_int(value):
    try:
        return int(value)
    except:
        return None


# =====================================================================
# IMPORTAR USERS
# =====================================================================
print("A carregar users.csv ...")

nrows = 20000 if LIMITED else None

users = pd.read_csv(
    "users.csv",
    sep=";",
    encoding="ISO-8859-1",
    on_bad_lines="skip",
    nrows=nrows
)

users = users.drop_duplicates(subset=["User-ID"])

user_docs = []
for _, row in users.iterrows():
    user_docs.append({
        "user_id": int(row["User-ID"]),
        "location": str(row["Location"]) if pd.notna(row["Location"]) else None,
        "age": safe_int(row["Age"])
    })

if user_docs:
    db.users.insert_many(user_docs, ordered=False)

print(f"Users inseridos: {db.users.count_documents({})}\n")


# =====================================================================
# IMPORTAR RATINGS — VERSÃO OTIMIZADA + LIMIT
# =====================================================================
print("A carregar ratings.csv ...")

ratings = pd.read_csv(
    "ratings.csv",
    sep=";",
    encoding="ISO-8859-1",
    on_bad_lines="skip",
    nrows=nrows
)

print(f"Linhas de ratings carregadas: {len(ratings):,}")
print("A agrupar ratings por ISBN ...")

ratings_by_isbn = defaultdict(list)

for _, row in ratings.iterrows():
    isbn = str(row["ISBN"])
    user_id = safe_int(row["User-ID"])
    rating = safe_int(row["Book-Rating"])

    if isbn and user_id is not None:
        ratings_by_isbn[isbn].append({
            "user_id": user_id,
            "book_rating": rating
        })

print(f"ISBN únicos: {len(ratings_by_isbn):,}")
print("A inserir documentos de book_ratings...")

batch = []
batch_size = 2000
count = 0

for isbn, list_ratings in ratings_by_isbn.items():
    batch.append({
        "ISBN": isbn,
        "ratings": list_ratings
    })

    if len(batch) >= batch_size:
        db.book_ratings.insert_many(batch, ordered=False)
        count += len(batch)
        print(f"  → {count:,} documentos inseridos...")
        batch = []

if batch:
    db.book_ratings.insert_many(batch, ordered=False)
    count += len(batch)

print(f"Total de documentos book_ratings inseridos: {count:,}\n")


# =====================================================================
# RESUMO FINAL
# =====================================================================
print("Resumo final:")
print("  Users:", db.users.count_documents({}))
print("  Book_Ratings:", db.book_ratings.count_documents({}))

client.close()
print("\nImportação concluída com sucesso!")
