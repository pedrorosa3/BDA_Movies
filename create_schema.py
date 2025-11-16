from pymongo import MongoClient

# ============================================================
# MONGODB LOCAL (DOCKER)
# ============================================================
MONGO_USER = "root"
MONGO_PASS = "<password>"
MONGO_HOST = "localhost"
MONGO_PORT = 27017
DB_NAME = "bda_Group11"

client = MongoClient(f"mongodb://{MONGO_USER}:{MONGO_PASS}@{MONGO_HOST}:{MONGO_PORT}/")
db = client[DB_NAME]
print(f"Ligado ao MongoDB local em {MONGO_HOST}:{MONGO_PORT}\n")

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

print(f"\nBase de dados '{DB_NAME}' criada no MongoDB local.")
client.close()
