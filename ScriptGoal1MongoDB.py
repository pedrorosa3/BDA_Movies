from pymongo import MongoClient


ATLAS_URI = "mongodb+srv://guiti03_db_user:<password>@cluster0.ezv71oa.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"

client = MongoClient(ATLAS_URI)
db = client["bda_Group11"]


for col in ["ratings", "books", "users"]:
    if col in db.list_collection_names():
        db[col].drop()
print("Coleções antigas removidas.\n")


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
db.users.create_index("user_id", unique=True) #Se tentarem inserir dois users com ids iguais, dá erro. É o correspondente a definir a primary key em SQL
print("Coleção 'users' criada com sucesso.")



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
            "image_url_l": {"bsonType": ["string", "null"], "description": "Imagem grande"}
        }
    }
}

db.create_collection("books", validator=books_schema)
db.books.create_index("ISBN", unique=True) #Dois books com ids iguais = erro
print("Coleção 'books' criada com sucesso.")


ratings_schema = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["user_id", "ISBN"],
        "properties": {
            "user_id": {"bsonType": "int", "description": "ID do utilizador"},
            "ISBN": {"bsonType": "string", "description": "ISBN do livro"},
            "book_rating": {"bsonType": ["int", "null"], "description": "Classificação atribuída"}
        }
    }
}

db.create_collection("ratings", validator=ratings_schema)
db.ratings.create_index([("user_id", 1), ("ISBN", 1)], unique=True)
print("Coleção 'ratings' criada com sucesso.")


print("\n Base de dados e coleções criadas com sucesso no MongoDB Atlas (bda_Group11).")
client.close()
