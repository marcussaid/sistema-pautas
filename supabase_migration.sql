-- Criação da tabela users
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    is_superuser BOOLEAN DEFAULT FALSE
);

-- Criação da tabela registros
CREATE TABLE IF NOT EXISTS registros (
    id SERIAL PRIMARY KEY,
    data DATE,
    demanda TEXT,
    assunto TEXT,
    status TEXT,
    local TEXT,
    direcionamentos TEXT,
    ultimo_editor TEXT,
    data_ultima_edicao TIMESTAMP WITH TIME ZONE,
    anexos JSONB DEFAULT '[]'::jsonb
);

-- Criação da tabela system_logs
CREATE TABLE IF NOT EXISTS system_logs (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    username TEXT,
    action TEXT,
    details TEXT,
    ip_address TEXT,
    message TEXT,
    level TEXT DEFAULT 'info',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
