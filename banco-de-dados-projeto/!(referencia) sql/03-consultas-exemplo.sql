

USE elo_db;


SELECT
    a.id_aluno,
    CONCAT(a.nome, ' ', a.sobrenome) AS aluno,
    a.usuario AS usuario_aluno,
    CONCAT(p.nome, ' ', p.sobrenome) AS professor,
    CONCAT(r.nome, ' ', r.sobrenome) AS responsavel
FROM vinculo AS v
INNER JOIN aluno AS a ON a.id_aluno = v.id_aluno
INNER JOIN professor AS p ON p.id_professor = v.id_professor
INNER JOIN responsavel AS r ON r.id_responsavel = v.id_responsavel
WHERE v.ativo = TRUE
ORDER BY a.nome, a.sobrenome;


SELECT
    m.id_meta,
    m.titulo,
    m.descricao,
    m.data_inicio,
    m.data_prazo,
    m.status_meta
FROM meta AS m
INNER JOIN aluno AS a ON a.id_aluno = m.id_aluno
WHERE a.usuario = 'maria.oliveira'
ORDER BY m.data_prazo;


SELECT
    atv.id_atividade,
    atv.titulo,
    atv.descricao,
    atv.data_entrega,
    COALESCE(m.titulo, 'Atividade extra') AS meta_relacionada
FROM atividade AS atv
INNER JOIN aluno AS a ON a.id_aluno = atv.id_aluno
LEFT JOIN meta AS m ON m.id_meta = atv.id_meta
WHERE a.usuario = 'maria.oliveira'
  AND atv.status_atividade = 'PENDENTE'
ORDER BY atv.data_entrega;


SELECT
    SUM(status_meta = 'EM_ANDAMENTO') AS metas_em_andamento,
    SUM(status_meta = 'CONCLUIDA') AS metas_concluidas
FROM meta AS m
INNER JOIN aluno AS a ON a.id_aluno = m.id_aluno
WHERE a.usuario = 'maria.oliveira';


SELECT
    f.data_acompanhamento,
    IF(f.compareceu, 'Presente', 'Ausente') AS situacao,
    f.observacao,
    CONCAT(p.nome, ' ', p.sobrenome) AS professor
FROM frequencia AS f
INNER JOIN aluno AS a ON a.id_aluno = f.id_aluno
INNER JOIN professor AS p ON p.id_professor = f.id_professor
WHERE a.usuario = 'maria.oliveira'
ORDER BY f.data_acompanhamento DESC;

