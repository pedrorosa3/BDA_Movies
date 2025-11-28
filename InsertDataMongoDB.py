from pymongo import MongoClient
import pandas as pd
from collections import defaultdict

# =====================================================================
# CONFIGURAÇÕES PRINCIPAIS
# =====================================================================
USE_LOCAL_DB = True      # True → ligar à BD local; False → ligar ao MongoDB Atlas
LIMITED = False          # True → carregar apenas 20.000 linhas (modo rápido)

# =====================================================================
# CONEXÃO AO MONGO
# =====================================================================
if USE_LOCAL_DB:
    # Credenciais e host da BD local
    MONGO_USER = "root"
    MONGO_PASS = "<password>"
    MONGO_HOST = "localhost"
    MONGO_PORT = "27017"
    DB_NAME = "bda_Group11"

    # URI para ligação local (com autenticação)
    URI = f"mongodb://{MONGO_USER}:{MONGO_PASS}@{MONGO_HOST}:{MONGO_PORT}/"
    client = MongoClient(URI)
else:
    # Ligação ao MongoDB Atlas (cloud)
    ATLAS_URI = "mongodb+srv://diogosfb91_db_user:<password>@cluster0.hszfcsx.mongodb.net/?appName=Cluster0"
    client = MongoClient(ATLAS_URI)
    DB_NAME = "bda_Group11"

db = client[DB_NAME]
print("Ligação ao MongoDB estabelecida.\n")


# =====================================================================
# APAGAR COLEÇÕES ANTIGAS
# (evita duplicação e garante que importação é limpa)
# =====================================================================
for col in ["users", "book_ratings"]:
    if col in db.list_collection_names():
        db[col].drop()

print("Coleções antigas removidas.\n")


# =====================================================================
# FUNÇÃO AUXILIAR — converter valores para inteiro de forma segura
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

nrows = 20000 if LIMITED else None   # limitar linhas (modo rápido)

users = pd.read_csv(
    "users.csv",
    sep=";",
    encoding="ISO-8859-1",
    on_bad_lines="skip",
    nrows=nrows
)

# Remover duplicados pelo ID
users = users.drop_duplicates(subset=["User-ID"])

# Criar documentos para inserir no Mongo
user_docs = []
for _, row in users.iterrows():
    user_docs.append({
        "user_id": int(row["User-ID"]),                           # ID do utilizador
        "location": str(row["Location"]) if pd.notna(row["Location"]) else None,
        "age": safe_int(row["Age"])                               # idade pode ser inválida → safe_int
    })

# Inserir em bulk
if user_docs:
    db.users.insert_many(user_docs, ordered=False)

print(f"Users inseridos: {db.users.count_documents({})}\n")


# =====================================================================
# IMPORTAR RATINGS (VERSÃO OTIMIZADA)
# Agrupar ratings pelo ISBN → reduz drasticamente o número de documentos
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

# ratings_by_isbn["ISBN"] = lista de ratings
ratings_by_isbn = defaultdict(list)

for _, row in ratings.iterrows():
    isbn = str(row["ISBN"])
    user_id = safe_int(row["User-ID"])
    rating = safe_int(row["Book-Rating"])

    # Apenas inserir ratings válidos
    if isbn and (user_id is not None):
        ratings_by_isbn[isbn].append({
            "user_id": user_id,
            "book_rating": rating
        })

print(f"ISBN únicos: {len(ratings_by_isbn):,}")
print("A inserir documentos de book_ratings...")

batch = []
batch_size = 2000
count = 0

# Inserção em batches (evita explosão de memória e velocidade máxima)
for isbn, list_ratings in ratings_by_isbn.items():
    batch.append({
        "ISBN": isbn,
        "ratings": list_ratings   # array de ratings deste ISBN
    })

    if len(batch) >= batch_size:
        db.book_ratings.insert_many(batch, ordered=False)
        count += len(batch)
        print(f"  → {count:,} documentos inseridos...")
        batch = []

# Inserir o último batch (se existir)
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
