from pymongo import MongoClient
import pandas as pd
from collections import defaultdict
from config import Config

# =====================================================================
# CONEXÃO AO MONGO
# =====================================================================
client = MongoClient(Config.build_mongo_uri())
db = client[Config.MONGO_DB]
print(f"Ligado ao MongoDB local em {Config.MONGO_HOST}:{Config.MONGO_PORT}\n")


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

if Config.LIMITED == "True":  # Está em string porque o .env só suporta str
    nrows = 20000
else: 
    nrows= None

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

import consistency_crossover as consistency

# correr o script
consistency.main()
# =====================================================================
# RESUMO FINAL
# =====================================================================
print("Resumo final:")
print("  Users:", db.users.count_documents({}))
print("  Book_Ratings:", db.book_ratings.count_documents({}))

client.close()
print("\nImportação concluída com sucesso!")
