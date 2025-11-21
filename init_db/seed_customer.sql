-- Seed default customer for the invoice handler system
-- This customer is automatically created with ID=1

INSERT INTO customers (id, name, email, phone, address, created_at, updated_at)
VALUES (
    1,
    'Default Customer',
    'default@example.com',
    NULL,
    NULL,
    NOW(),
    NOW()
)
ON CONFLICT (id) DO NOTHING;

-- Reset sequence to ensure next customer gets ID > 1
SELECT setval('customers_id_seq', (SELECT MAX(id) FROM customers));

