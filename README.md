# BDA_Group11
BDA_Group11


Os ratings devem de estar na coleção livros, não numa coleção à parte - Versão do Mongo


## GOAL 2 

Queries que foram feitas em SQL :

- 1 - Top 10 livros com melhor avaliação

- 2 - Histórico de avaliações de um utilizador específico (Perguntar ao stor se pode ser como está em que tem de ser definido manualmente - caso seja escáfia, remover)

- 3 - Autores com melhor média de classificação (mínimo 50 avaliações totais)

- 4 - Editoras com livros mais bem classificados

- 5 - Top 10 utilizadores mais ativos - Query para combinar com Mongo.

- 6 -  Top livros por faixa etária - Deslimitar para ver mais faixas etárias, senao aparece só a primeira.

- 7 - Utilizadores com gostos semelhantes (simples)
     Encontra pares de utilizadores que deram ratings idênticos ao mesmo livro.

- 8 - Sugere livros que um utilizador ainda não leu, mas que são   bem avaliados por utilizadores semelhantes.
Exemplo está com utilizador 277427.

 -Esta está a demorar imenso tempo, até tive de aumentar o timeout.
 -Talvez usar indexs

- 9 - Mostra a média de classificação e o número de livros avaliados por ano.

- 10 - Autores mais populares entre joven (até 25 anos)

# Para criar mongoDB num container docker
No terminal ir até ao repo e:
- docker pull mongo
- docker-compose up -d
- docker exec -it mongodb mongosh -u root -p <password> (Para testar)
- python create_schema.py

Depois de ter a bd no container criada falta popular. Para isso basta rodarem o InsertDataMongoDB,
mas vejam as duas variaveis no inicio do script. Mudar a gosto.
