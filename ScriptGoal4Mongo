// Ponto 1 - Índices para melhorar performance das queries


// Para buscar utilizadores rapidamente
db.users.createIndex({ user_id: 1 }, { unique: true });

// Para aceder ratings por livro
db.book_ratings.createIndex({ ISBN: 1 });

// Se fizerem queries por user dentro de arrays
db.book_ratings.createIndex({ "ratings.user_id": 1 });


// Ponto 2 - Agregação para leitura mais eficiente
//evita unwind sempre que querem a média
db.book_ratings.aggregate([
  { $unwind: "$ratings" },
  { $group: {
      _id: "$ISBN",
      total: { $sum: 1 },
      avg: { $avg: "$ratings.book_rating" }
  }},
  { $merge: { into: "book_stats", whenMatched: "replace" }}
]);


