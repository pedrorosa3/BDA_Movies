from pymongo import MongoClient
from config import Config

# ============================================================
# MONGODB LOCAL (DOCKER)
# ============================================================
client = MongoClient(Config.build_mongo_uri())
db = client[Config.MONGO_DB]
print(f"Ligado ao MongoDB local em {Config.MONGO_HOST}:{Config.MONGO_PORT}\n")

# ============================================================
# LIMPAR COLEÇÕES ANTIGAS
# ============================================================
for col in db.list_collection_names():
    db[col].drop()
print("Todas as coleções anteriores removidas.\n")

# ============================================================
# COLEÇÃO: users
# ============================================================
users_schema = {
    "$jsonSchema": {
        "bsonType": "object",                     # O documento principal deve ser um objeto
        "required": ["user_id"],                  # user_id é obrigatório
        "properties": {
            "user_id": {"bsonType": "int"},       # user_id tem de ser inteiro
            "location": {"bsonType": ["string", "null"]},  # localização pode ser string ou null
            "age": {"bsonType": ["int", "null"]} # idade pode ser inteira ou null
        }
    }
}

db.create_collection("users", validator=users_schema)
db.users.create_index("user_id", unique=True)
print("Coleção 'users' criada com sucesso.")

# ============================================================
# COLEÇÃO: book_ratings
# ============================================================
book_ratings_schema = {
    "$jsonSchema": {
        "bsonType": "object",                             # Documento principal é um objeto
        "required": ["ISBN"],                             # ISBN é obrigatório
        "properties": {
            "ISBN": {"bsonType": "string"},               # ISBN deve ser string

            "ratings": {                                  # ratings é um array
                "bsonType": ["array"],
                "items": {
                    "bsonType": "object",                 # cada item do array é um objeto
                    "required": ["user_id", "book_rating"],  # ambos obrigatórios
                    "properties": {
                        "user_id": {"bsonType": "int"},   # user_id é inteiro
                        "book_rating": {"bsonType": ["int", "null"]}  # rating pode ser int ou null
                    }
                }
            }
        }
    }
}

db.create_collection("book_ratings", validator=book_ratings_schema)
db.book_ratings.create_index("ISBN", unique=True)
print("Coleção 'book_ratings' criada com sucesso.")

print(f"\nBase de dados '{Config.DB_NAME}' criada no MongoDB local.")
client.close()
