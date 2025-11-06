from pymongo import MongoClient

# ---- CONEXÃO AO MONGODB ATLAS ----
ATLAS_URI = "mongodb+srv://diogosfb91_db_user:<password>@cluster0.hszfcsx.mongodb.net/?appName=Cluster0"
client = MongoClient(ATLAS_URI)
db = client["bda_Group11"]

# ---- LIMPAR COLEÇÕES ANTIGAS ----
for col in ["books", "users"]:
    if col in db.list_collection_names():
        db[col].drop()
print("Coleções antigas removidas.\n")

# ---- users ----
users_schema = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["user_id"],
        "properties": {
            "user_id": {"bsonType": "int", "description": "Identificador único do utilizador"},
            "location": {"bsonType": ["string", "null"], "description": "Localização do utilizador"},
            "age": {"bsonType": ["int", "null"], "description": "Idade (pode ser nula)"}
        }
    }
}

db.create_collection("users", validator=users_schema)
db.users.create_index("user_id", unique=True)
print("Coleção 'users' criada com sucesso.")


# ---- books (com ratings embutidos) ----
books_schema = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["ISBN"],
        "properties": {
            "ISBN": {"bsonType": "string", "description": "Código ISBN"},
            "book_title": {"bsonType": ["string", "null"], "description": "Título do livro"},
            "book_author": {"bsonType": ["string", "null"], "description": "Autor"},
            "year_of_publication": {"bsonType": ["int", "null"], "description": "Ano de publicação"},
            "publisher": {"bsonType": ["string", "null"], "description": "Editora"},
            "image_url_s": {"bsonType": ["string", "null"], "description": "Imagem pequena"},
            "image_url_m": {"bsonType": ["string", "null"], "description": "Imagem média"},
            "image_url_l": {"bsonType": ["string", "null"], "description": "Imagem grande"},
            "ratings": {
                "bsonType": ["array"],
                "items": {
                    "bsonType": "object",
                    "required": ["user_id", "book_rating"],
                    "properties": {
                        "user_id": {"bsonType": "int", "description": "ID do utilizador"},
                        "book_rating": {"bsonType": ["int", "null"], "description": "Classificação atribuída"}
                    }
                },
                "description": "Lista de avaliações deste livro"
            }
        }
    }
}

db.create_collection("books", validator=books_schema)
db.books.create_index("ISBN", unique=True)
print("Coleção 'books' criada com sucesso (com campo ratings embutido).")

print("\nBase de dados criada com sucesso no MongoDB Atlas (bda_Group11).")
client.close()
