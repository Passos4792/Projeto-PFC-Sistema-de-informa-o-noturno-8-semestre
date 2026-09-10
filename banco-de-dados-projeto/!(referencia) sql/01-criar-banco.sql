/*
    PROJETO ELO - CRIAÇÃO DO BANCO DE DADOS

    Este arquivo cria somente o banco e suas tabelas.
    Ele não possui ligação com HTML, CSS, JavaScript ou Django.

    Banco preparado para MySQL 8.
*/

/* Cria o banco sem apagar um banco existente. */
CREATE DATABASE IF NOT EXISTS elo_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

/* Define elo_db como o banco utilizado pelos próximos comandos. */
USE elo_db;

/*
    Tabela de professores.
    O campo usuario substitui o e-mail e será formado pelo nome e sobrenome.
*/
CREATE TABLE IF NOT EXISTS professor (
    id_professor INT UNSIGNED NOT NULL AUTO_INCREMENT,
    nome VARCHAR(80) NOT NULL,
    sobrenome VARCHAR(120) NOT NULL,
    usuario VARCHAR(160) NOT NULL,
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id_professor),
    UNIQUE KEY uk_professor_usuario (usuario)
) ENGINE = InnoDB;

/* Tabela das pessoas responsáveis pelos alunos. */
CREATE TABLE IF NOT EXISTS responsavel (
    id_responsavel INT UNSIGNED NOT NULL AUTO_INCREMENT,
    nome VARCHAR(80) NOT NULL,
    sobrenome VARCHAR(120) NOT NULL,
    usuario VARCHAR(160) NOT NULL,
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id_responsavel),
    UNIQUE KEY uk_responsavel_usuario (usuario)
) ENGINE = InnoDB;

/* Tabela dos alunos acompanhados pelo projeto ELO. */
CREATE TABLE IF NOT EXISTS aluno (
    id_aluno INT UNSIGNED NOT NULL AUTO_INCREMENT,
    nome VARCHAR(80) NOT NULL,
    sobrenome VARCHAR(120) NOT NULL,
    usuario VARCHAR(160) NOT NULL,
    data_nascimento DATE NULL,
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id_aluno),
    UNIQUE KEY uk_aluno_usuario (usuario)
) ENGINE = InnoDB;

/*
    FUNCIONALIDADE 2 - VÍNCULOS

    Une um aluno ao professor e ao responsável que o acompanham.
    Nesta primeira versão, cada aluno terá somente um vínculo ativo.
*/
CREATE TABLE IF NOT EXISTS vinculo (
    id_vinculo INT UNSIGNED NOT NULL AUTO_INCREMENT,
    id_aluno INT UNSIGNED NOT NULL,
    id_professor INT UNSIGNED NOT NULL,
    id_responsavel INT UNSIGNED NOT NULL,
    data_vinculo DATE NOT NULL,
    ativo BOOLEAN NOT NULL DEFAULT TRUE,

    PRIMARY KEY (id_vinculo),
    UNIQUE KEY uk_vinculo_aluno (id_aluno),
    KEY idx_vinculo_professor (id_professor),
    KEY idx_vinculo_responsavel (id_responsavel),

    CONSTRAINT fk_vinculo_aluno
        FOREIGN KEY (id_aluno) REFERENCES aluno (id_aluno)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_vinculo_professor
        FOREIGN KEY (id_professor) REFERENCES professor (id_professor)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_vinculo_responsavel
        FOREIGN KEY (id_responsavel) REFERENCES responsavel (id_responsavel)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE = InnoDB;

/*
    FUNCIONALIDADE 3 - METAS

    Cada meta pertence a um aluno e é criada por um professor.
*/
CREATE TABLE IF NOT EXISTS meta (
    id_meta INT UNSIGNED NOT NULL AUTO_INCREMENT,
    id_aluno INT UNSIGNED NOT NULL,
    id_professor INT UNSIGNED NOT NULL,
    titulo VARCHAR(150) NOT NULL,
    descricao TEXT NULL,
    data_inicio DATE NOT NULL,
    data_prazo DATE NULL,
    status_meta ENUM('EM_ANDAMENTO', 'CONCLUIDA', 'CANCELADA') NOT NULL DEFAULT 'EM_ANDAMENTO',
    criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id_meta),
    KEY idx_meta_aluno (id_aluno),
    KEY idx_meta_professor (id_professor),
    KEY idx_meta_status (status_meta),

    CONSTRAINT fk_meta_aluno
        FOREIGN KEY (id_aluno) REFERENCES aluno (id_aluno)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_meta_professor
        FOREIGN KEY (id_professor) REFERENCES professor (id_professor)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT chk_meta_datas
        CHECK (data_prazo IS NULL OR data_prazo >= data_inicio)
) ENGINE = InnoDB;

/*
    FUNCIONALIDADE 3 - ATIVIDADES

    A atividade pode estar ligada a uma meta.
    id_meta aceita NULL porque também poderão existir atividades extras.
*/
CREATE TABLE IF NOT EXISTS atividade (
    id_atividade INT UNSIGNED NOT NULL AUTO_INCREMENT,
    id_aluno INT UNSIGNED NOT NULL,
    id_professor INT UNSIGNED NOT NULL,
    id_meta INT UNSIGNED NULL,
    titulo VARCHAR(150) NOT NULL,
    descricao TEXT NULL,
    data_entrega DATE NULL,
    status_atividade ENUM('PENDENTE', 'CONCLUIDA', 'CANCELADA') NOT NULL DEFAULT 'PENDENTE',
    criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id_atividade),
    KEY idx_atividade_aluno (id_aluno),
    KEY idx_atividade_professor (id_professor),
    KEY idx_atividade_meta (id_meta),
    KEY idx_atividade_status (status_atividade),

    CONSTRAINT fk_atividade_aluno
        FOREIGN KEY (id_aluno) REFERENCES aluno (id_aluno)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_atividade_professor
        FOREIGN KEY (id_professor) REFERENCES professor (id_professor)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_atividade_meta
        FOREIGN KEY (id_meta) REFERENCES meta (id_meta)
        ON UPDATE CASCADE ON DELETE SET NULL
) ENGINE = InnoDB;

/* Conteúdos de apoio enviados pelo professor para o aluno. */
CREATE TABLE IF NOT EXISTS conteudo (
    id_conteudo INT UNSIGNED NOT NULL AUTO_INCREMENT,
    id_aluno INT UNSIGNED NOT NULL,
    id_professor INT UNSIGNED NOT NULL,
    id_atividade INT UNSIGNED NULL,
    titulo VARCHAR(150) NOT NULL,
    descricao TEXT NULL,
    tipo_conteudo VARCHAR(40) NULL,
    criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id_conteudo),
    KEY idx_conteudo_aluno (id_aluno),
    KEY idx_conteudo_professor (id_professor),
    KEY idx_conteudo_atividade (id_atividade),

    CONSTRAINT fk_conteudo_aluno
        FOREIGN KEY (id_aluno) REFERENCES aluno (id_aluno)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_conteudo_professor
        FOREIGN KEY (id_professor) REFERENCES professor (id_professor)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_conteudo_atividade
        FOREIGN KEY (id_atividade) REFERENCES atividade (id_atividade)
        ON UPDATE CASCADE ON DELETE SET NULL
) ENGINE = InnoDB;

/* Registros de presença nos acompanhamentos realizados. */
CREATE TABLE IF NOT EXISTS frequencia (
    id_frequencia INT UNSIGNED NOT NULL AUTO_INCREMENT,
    id_aluno INT UNSIGNED NOT NULL,
    id_professor INT UNSIGNED NOT NULL,
    data_acompanhamento DATE NOT NULL,
    compareceu BOOLEAN NOT NULL DEFAULT TRUE,
    observacao VARCHAR(255) NULL,
    criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id_frequencia),
    KEY idx_frequencia_aluno (id_aluno),
    KEY idx_frequencia_professor (id_professor),
    KEY idx_frequencia_data (data_acompanhamento),

    CONSTRAINT fk_frequencia_aluno
        FOREIGN KEY (id_aluno) REFERENCES aluno (id_aluno)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_frequencia_professor
        FOREIGN KEY (id_professor) REFERENCES professor (id_professor)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE = InnoDB;

/* Exibe as tabelas criadas para facilitar a conferência no Workbench. */
SHOW TABLES;
