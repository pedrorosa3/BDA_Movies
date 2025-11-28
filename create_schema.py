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
        "bsonType": "object",
        "required": ["user_id"],
        "properties": {
            "user_id": {"bsonType": "int"},
            "location": {"bsonType": ["string", "null"]},
            "age": {"bsonType": ["int", "null"]}
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
        "bsonType": "object",
        "required": ["ISBN"],
        "properties": {
            "ISBN": {"bsonType": "string"},

            "ratings": {
                "bsonType": ["array"],
                "items": {
                    "bsonType": "object",
                    "required": ["user_id", "book_rating"],
                    "properties": {
                        "user_id": {"bsonType": "int"},
                        "book_rating": {"bsonType": ["int", "null"]}
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
