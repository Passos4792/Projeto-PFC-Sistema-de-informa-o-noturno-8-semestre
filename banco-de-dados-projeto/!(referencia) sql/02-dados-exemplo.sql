/*
    PROJETO ELO - DADOS DE EXEMPLO

    Execute este arquivo depois de 01-criar-banco.sql.
    Estes registros servem somente para testar o banco nesta primeira versão.
*/

USE elo_db;

/* Professores apresentados na tela de professores. */
INSERT IGNORE INTO professor
    (id_professor, nome, sobrenome, usuario, ativo)
VALUES
    (1, 'Ana', 'Martins', 'ana.martins', TRUE),
    (2, 'Carlos', 'Souza', 'carlos.souza', TRUE),
    (3, 'Fernanda', 'Lima', 'fernanda.lima', TRUE);

/* Responsáveis usados nos vínculos de exemplo. */
INSERT IGNORE INTO responsavel
    (id_responsavel, nome, sobrenome, usuario, ativo)
VALUES
    (1, 'Paula', 'Oliveira', 'paula.oliveira', TRUE),
    (2, 'Roberto', 'Costa', 'roberto.costa', TRUE),
    (3, 'Juliana', 'Santos', 'juliana.santos', TRUE);

/* Alunos acompanhados pelo sistema. */
INSERT IGNORE INTO aluno
    (id_aluno, nome, sobrenome, usuario, data_nascimento, ativo)
VALUES
    (1, 'Maria', 'Oliveira', 'maria.oliveira', '2012-05-14', TRUE),
    (2, 'Lucas', 'Costa', 'lucas.costa', '2011-09-22', TRUE),
    (3, 'Beatriz', 'Santos', 'beatriz.santos', '2013-02-10', TRUE);

/* Cada aluno recebe um professor e um responsável. */
INSERT IGNORE INTO vinculo
    (id_vinculo, id_aluno, id_professor, id_responsavel, data_vinculo, ativo)
VALUES
    (1, 1, 1, 1, '2026-08-10', TRUE),
    (2, 2, 2, 2, '2026-08-11', TRUE),
    (3, 3, 3, 3, '2026-08-12', TRUE);

/* Metas que alimentam os exemplos da tela inicial da aluna Maria. */
INSERT IGNORE INTO meta
    (id_meta, id_aluno, id_professor, titulo, descricao, data_inicio, data_prazo, status_meta)
VALUES
    (1, 1, 1, 'Melhorar a leitura', 'Ler durante vinte minutos por dia.', '2026-08-10', '2026-09-30', 'EM_ANDAMENTO'),
    (2, 1, 1, 'Criar rotina de estudos', 'Separar um horário para estudar durante a semana.', '2026-08-10', '2026-10-15', 'EM_ANDAMENTO'),
    (3, 1, 1, 'Organizar o material', 'Manter livros e cadernos organizados.', '2026-08-01', '2026-08-20', 'CONCLUIDA'),
    (4, 1, 1, 'Expressar emoções', 'Registrar como se sentiu durante a semana.', '2026-08-01', '2026-08-25', 'CONCLUIDA');

/* Atividades da semana apresentadas na tela do aluno. */
INSERT IGNORE INTO atividade
    (id_atividade, id_aluno, id_professor, id_meta, titulo, descricao, data_entrega, status_atividade)
VALUES
    (1, 1, 1, 1, 'Tarefa', 'Ler e escrever um resumo sobre o livro entregue na sexta.', '2026-09-11', 'PENDENTE'),
    (2, 1, 1, 4, 'Emoções', 'Fazer um diário de emoções dos fins de semana.', '2026-09-14', 'PENDENTE'),
    (3, 1, 1, NULL, 'Extra', 'Realizar atividade musical ensinada em sala com os pais.', '2026-09-18', 'PENDENTE');

/* Conteúdos simples associados às atividades. */
INSERT IGNORE INTO conteudo
    (id_conteudo, id_aluno, id_professor, id_atividade, titulo, descricao, tipo_conteudo)
VALUES
    (1, 1, 1, 1, 'Guia para o resumo', 'Passos para organizar o resumo do livro.', 'TEXTO'),
    (2, 1, 1, 2, 'Modelo de diário', 'Perguntas que ajudam a registrar as emoções.', 'TEXTO');

/* Registros de frequência de exemplo. */
INSERT IGNORE INTO frequencia
    (id_frequencia, id_aluno, id_professor, data_acompanhamento, compareceu, observacao)
VALUES
    (1, 1, 1, '2026-08-14', TRUE, 'Participou das atividades propostas.'),
    (2, 1, 1, '2026-08-21', TRUE, 'Apresentou evolução na leitura.'),
    (3, 1, 1, '2026-08-28', FALSE, 'Ausência informada pelo responsável.');

/* Confirma quantos registros foram inseridos em cada tabela principal. */
SELECT 'professor' AS tabela, COUNT(*) AS quantidade FROM professor
UNION ALL
SELECT 'responsavel', COUNT(*) FROM responsavel
UNION ALL
SELECT 'aluno', COUNT(*) FROM aluno
UNION ALL
SELECT 'vinculo', COUNT(*) FROM vinculo
UNION ALL
SELECT 'meta', COUNT(*) FROM meta
UNION ALL
SELECT 'atividade', COUNT(*) FROM atividade
UNION ALL
SELECT 'conteudo', COUNT(*) FROM conteudo
UNION ALL
SELECT 'frequencia', COUNT(*) FROM frequencia;
