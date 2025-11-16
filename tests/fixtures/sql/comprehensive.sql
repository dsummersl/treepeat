-- Comprehensive SQL fixture for testing
-- This file demonstrates various SQL constructs

-- Create database and tables
CREATE DATABASE IF NOT EXISTS test_db;
USE test_db;

-- Users table
CREATE TABLE users (
    id INT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    INDEX idx_username (username),
    INDEX idx_email (email)
);

-- Posts table
CREATE TABLE posts (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    title VARCHAR(200) NOT NULL,
    content TEXT,
    status ENUM('draft', 'published', 'archived') DEFAULT 'draft',
    published_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_id (user_id),
    INDEX idx_status (status)
);

-- Comments table
CREATE TABLE comments (
    id INT PRIMARY KEY AUTO_INCREMENT,
    post_id INT NOT NULL,
    user_id INT NOT NULL,
    comment_text TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Insert sample data
INSERT INTO users (username, email, password_hash) VALUES
    ('john_doe', 'john@example.com', 'hashed_password_1'),
    ('jane_smith', 'jane@example.com', 'hashed_password_2'),
    ('bob_jones', 'bob@example.com', 'hashed_password_3');

INSERT INTO posts (user_id, title, content, status) VALUES
    (1, 'First Post', 'This is the content of the first post', 'published'),
    (1, 'Draft Post', 'This is a draft', 'draft'),
    (2, 'Jane''s Post', 'Content from Jane', 'published');

-- SELECT queries
-- Simple select
SELECT * FROM users;

-- Select with WHERE clause
SELECT username, email FROM users WHERE is_active = TRUE;

-- Join query
SELECT
    u.username,
    p.title,
    p.status,
    p.created_at
FROM users u
INNER JOIN posts p ON u.id = p.user_id
WHERE p.status = 'published'
ORDER BY p.created_at DESC;

-- Aggregate query
SELECT
    u.username,
    COUNT(p.id) AS post_count
FROM users u
LEFT JOIN posts p ON u.id = p.user_id
GROUP BY u.id, u.username
HAVING post_count > 0;

-- Subquery
SELECT username, email
FROM users
WHERE id IN (
    SELECT DISTINCT user_id
    FROM posts
    WHERE status = 'published'
);

-- Complex join with multiple tables
SELECT
    u.username,
    p.title AS post_title,
    COUNT(c.id) AS comment_count
FROM users u
INNER JOIN posts p ON u.id = p.user_id
LEFT JOIN comments c ON p.id = c.post_id
WHERE p.status = 'published'
GROUP BY u.id, u.username, p.id, p.title
ORDER BY comment_count DESC;

-- UPDATE statements
UPDATE users
SET updated_at = CURRENT_TIMESTAMP
WHERE id = 1;

UPDATE posts
SET status = 'published', published_at = CURRENT_TIMESTAMP
WHERE id = 2 AND status = 'draft';

-- DELETE statements
DELETE FROM comments WHERE created_at < DATE_SUB(NOW(), INTERVAL 1 YEAR);

-- Create view
CREATE VIEW active_users_with_posts AS
SELECT
    u.id,
    u.username,
    u.email,
    COUNT(p.id) AS post_count
FROM users u
LEFT JOIN posts p ON u.id = p.user_id
WHERE u.is_active = TRUE
GROUP BY u.id, u.username, u.email;

-- Create stored procedure
DELIMITER //
CREATE PROCEDURE GetUserPosts(IN user_id INT)
BEGIN
    SELECT
        p.id,
        p.title,
        p.content,
        p.status,
        p.created_at
    FROM posts p
    WHERE p.user_id = user_id
    ORDER BY p.created_at DESC;
END //
DELIMITER ;

-- Transaction example
START TRANSACTION;

UPDATE users SET is_active = FALSE WHERE id = 3;
DELETE FROM posts WHERE user_id = 3;

COMMIT;
