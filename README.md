# BDA_Group11
Diogo Sousa nº60250
Francisco Lopes nº60252
Guilherme Almeida nº60264
Pedro Rosa nº60294
## MongoDB Local
Pré‑requisitos:
```bash
py -m pip install mysql-connector-python pymongo pandas
```
Criar container do MongoDB:
```bash
docker pull mongo
docker-compose up -d
docker exec -it mongodb mongosh -u root -p <password>
```
Criar schema:
```bash
python create_schema.py
```
Popular a base de dados:
- Executar `InsertDataMongoDB.py`
- Validar e ajustar as variáveis no topo do script antes de correr.
## MySQL Local
Instalar:
- MySQL Server  
- MySQL Workbench  
Executar scripts na seguinte ordem:
1. `ScriptGoal1SQL.py` – cria a base de dados e tabelas.
2. `InsertDataSQL.py` – popula as tabelas SQL com os CSV.
3. `ScriptGoal4Master.py` – scripts finais agregados para o GOAL 4.