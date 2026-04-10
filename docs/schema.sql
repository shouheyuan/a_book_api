-- VisionNovel MySQL Schema
-- 运行: mysql -u root -p visionnovel < docs/schema.sql

CREATE DATABASE IF NOT EXISTS visionnovel CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE visionnovel;

-- 用户表
CREATE TABLE IF NOT EXISTS user_profiles (
    id            VARCHAR(36)  PRIMARY KEY,
    email         VARCHAR(255) UNIQUE NOT NULL,
    username      VARCHAR(100),
    password_hash VARCHAR(255),
    apple_user_id VARCHAR(255) UNIQUE,
    bio           TEXT,
    avatar_url    VARCHAR(500),
    coin_balance  INT          NOT NULL DEFAULT 0,
    created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_email (email)
) ENGINE=InnoDB;

-- 阅读进度
CREATE TABLE IF NOT EXISTS reading_sessions (
    id              VARCHAR(36)  PRIMARY KEY,
    user_id         VARCHAR(36)  NOT NULL,
    book_identifier VARCHAR(500) NOT NULL,
    book_title      VARCHAR(500),
    locator_json    TEXT,
    progression     FLOAT,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_user_book (user_id, book_identifier(200)),
    INDEX idx_user_id (user_id),
    FOREIGN KEY (user_id) REFERENCES user_profiles(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 笔记/高亮
CREATE TABLE IF NOT EXISTS annotations (
    id              VARCHAR(36) PRIMARY KEY,
    user_id         VARCHAR(36) NOT NULL,
    book_identifier VARCHAR(500),
    book_title      VARCHAR(500),
    highlight_text  TEXT,
    note            TEXT,
    locator_json    TEXT,
    color           VARCHAR(50),
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    INDEX idx_book (book_identifier(200)),
    FOREIGN KEY (user_id) REFERENCES user_profiles(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 书库
CREATE TABLE IF NOT EXISTS books (
    id         VARCHAR(36)  PRIMARY KEY,
    title      VARCHAR(500) NOT NULL,
    author     VARCHAR(255),
    cover_url  VARCHAR(500),
    identifier VARCHAR(500),
    description TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FULLTEXT INDEX ft_title_author (title, author)
) ENGINE=InnoDB;

-- 我的书架
CREATE TABLE IF NOT EXISTS user_bookshelf (
    id         VARCHAR(36)  PRIMARY KEY,
    user_id    VARCHAR(36)  NOT NULL,
    book_id    VARCHAR(36)  NOT NULL,
    title      VARCHAR(500),
    author     VARCHAR(255),
    cover_url  VARCHAR(500),
    identifier VARCHAR(500),
    added_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_user_book (user_id, book_id),
    INDEX idx_user_id (user_id),
    FOREIGN KEY (user_id) REFERENCES user_profiles(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- AI 生图记录
CREATE TABLE IF NOT EXISTS ai_images (
    id              VARCHAR(36) PRIMARY KEY,
    user_id         VARCHAR(36) NOT NULL,
    prompt          TEXT,
    image_url       VARCHAR(500),
    book_identifier VARCHAR(500),
    coins_used      INT DEFAULT 0,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    FOREIGN KEY (user_id) REFERENCES user_profiles(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- AI 改写记录
CREATE TABLE IF NOT EXISTS ai_revisions (
    id              VARCHAR(36) PRIMARY KEY,
    user_id         VARCHAR(36) NOT NULL,
    original_text   TEXT,
    revised_text    TEXT,
    book_identifier VARCHAR(500),
    coins_used      INT DEFAULT 0,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    FOREIGN KEY (user_id) REFERENCES user_profiles(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 书币流水
CREATE TABLE IF NOT EXISTS coin_transactions (
    id            VARCHAR(36) PRIMARY KEY,
    user_id       VARCHAR(36) NOT NULL,
    amount        INT         NOT NULL,
    description   VARCHAR(500),
    reference_id  VARCHAR(255),
    balance_after INT         NOT NULL,
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    FOREIGN KEY (user_id) REFERENCES user_profiles(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 合集
CREATE TABLE IF NOT EXISTS collections (
    id          VARCHAR(36)  PRIMARY KEY,
    user_id     VARCHAR(36)  NOT NULL,
    name        VARCHAR(255) NOT NULL,
    description TEXT,
    cover_url   VARCHAR(500),
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    FOREIGN KEY (user_id) REFERENCES user_profiles(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 合集-书关联
CREATE TABLE IF NOT EXISTS collection_books (
    id            VARCHAR(36) PRIMARY KEY,
    collection_id VARCHAR(36) NOT NULL,
    user_book_id  VARCHAR(36) NOT NULL,
    added_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_col_book (collection_id, user_book_id),
    FOREIGN KEY (collection_id) REFERENCES collections(id) ON DELETE CASCADE
) ENGINE=InnoDB;
