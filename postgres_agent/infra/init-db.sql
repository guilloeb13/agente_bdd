-- Sample database for testing PMA-Agent

-- Create test schema
CREATE SCHEMA IF NOT EXISTS app;

-- Users table
CREATE TABLE app.users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL,
    username VARCHAR(100) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);

-- Create index on email
CREATE INDEX idx_users_email ON app.users(email);

-- Products table (missing FK constraint intentionally)
CREATE TABLE app.products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    price NUMERIC(10, 2) NOT NULL,
    category_id INTEGER,  -- Missing FK
    stock_quantity INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Categories table
CREATE TABLE app.categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    parent_id INTEGER REFERENCES app.categories(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Orders table
CREATE TABLE app.orders (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES app.users(id),
    status VARCHAR(50) DEFAULT 'pending',
    total_amount NUMERIC(12, 2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    shipped_at TIMESTAMP  -- Missing timezone
);

-- Order items (wide table with repeating groups)
CREATE TABLE app.order_items (
    id SERIAL PRIMARY KEY,
    order_id INTEGER REFERENCES app.orders(id) ON DELETE CASCADE,
    product_id INTEGER REFERENCES app.products(id),
    quantity INTEGER NOT NULL,
    unit_price NUMERIC(10, 2) NOT NULL,
    -- Denormalized data
    product_name VARCHAR(255),
    product_category VARCHAR(100)
);

-- Audit log (large table candidate for partitioning)
CREATE TABLE app.audit_logs (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER,
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(100),
    entity_id INTEGER,
    old_values JSONB,
    new_values JSONB,
    ip_address INET,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Settings (low cardinality example)
CREATE TABLE app.settings (
    id SERIAL PRIMARY KEY,
    key VARCHAR(100) NOT NULL UNIQUE,
    value TEXT,
    type VARCHAR(20) DEFAULT 'string'  -- Low cardinality
);

-- Insert test data
INSERT INTO app.users (email, username, password_hash) VALUES
    ('admin@test.com', 'admin', 'hash1'),
    ('user1@test.com', 'user1', 'hash2'),
    ('user2@test.com', 'user2', 'hash3');

INSERT INTO app.categories (name, parent_id) VALUES
    ('Electronics', NULL),
    ('Computers', 1),
    ('Phones', 1),
    ('Clothing', NULL);

INSERT INTO app.products (name, price, category_id, stock_quantity) VALUES
    ('Laptop', 999.99, 2, 50),
    ('Phone', 599.99, 3, 100),
    ('T-Shirt', 29.99, 4, 200);

INSERT INTO app.orders (user_id, status, total_amount) VALUES
    (1, 'completed', 999.99),
    (2, 'pending', 629.98);

INSERT INTO app.settings (key, value, type) VALUES
    ('site_name', 'Test Store', 'string'),
    ('max_items', '100', 'integer'),
    ('enabled', 'true', 'boolean');

-- Create a SECURITY DEFINER function (for security analysis)
CREATE OR REPLACE FUNCTION app.get_user_orders(p_user_id INTEGER)
RETURNS TABLE (order_id INTEGER, total NUMERIC)
SECURITY DEFINER
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT id, total_amount
    FROM app.orders
    WHERE user_id = p_user_id;
END;
$$;

-- Create trigger function
CREATE OR REPLACE FUNCTION app.update_timestamp()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

-- Create trigger
CREATE TRIGGER users_update_timestamp
    BEFORE UPDATE ON app.users
    FOR EACH ROW
    EXECUTE FUNCTION app.update_timestamp();

-- Grant some permissions for testing
GRANT SELECT ON ALL TABLES IN SCHEMA app TO PUBLIC;

COMMENT ON TABLE app.users IS 'Application users';
COMMENT ON TABLE app.products IS 'Product catalog';
COMMENT ON COLUMN app.users.email IS 'User email address';
