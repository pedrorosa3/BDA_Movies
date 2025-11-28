from dotenv import load_dotenv
import os

# Carregar variáveis do .env
load_dotenv()

class Config:
    # ---------------------------
    # MySQL
    # ---------------------------
    MYSQL_HOST = os.getenv("MYSQL_HOST")
    MYSQL_USER = os.getenv("MYSQL_USER")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")
    MYSQL_DB = os.getenv("MYSQL_DB")

    # ---------------------------
    # MongoDB (URI completa)
    # ---------------------------
    MONGO_URI = os.getenv("MONGO_URI")

    # Base de dados (usada por MySQL & MongoBD)
    DB_NAME = os.getenv("DB_NAME")

    # ---------------------------
    # MongoDB (modo manual: host/port/user/pass)
    # ---------------------------
    MONGO_USER = os.getenv("MONGO_USER")
    MONGO_PASS = os.getenv("MONGO_PASS")
    MONGO_HOST = os.getenv("MONGO_HOST")
    MONGO_PORT = os.getenv("MONGO_PORT")
    MONGO_DB = os.getenv("MONGO_DB")
    
    LIMITED = os.getenv("LIMITED")

    # Função auxiliar: construir URI caso não exista
    @staticmethod
    def build_mongo_uri():
        """
        Constrói a URI manualmente caso MONGO_URI não esteja definida.
        """
        if Config.MONGO_URI:
            return Config.MONGO_URI
        
        # Construir manualmente
        user = Config.MONGO_USER
        password = Config.MONGO_PASS
        host = Config.MONGO_HOST
        port = Config.MONGO_PORT
        
        if user and password:
            return f"mongodb://{user}:{password}@{host}:{port}/"
        else:
            return f"mongodb://{host}:{port}/"

