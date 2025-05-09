-- Adiciona as novas colunas na tabela system_logs
ALTER TABLE system_logs ADD COLUMN IF NOT EXISTS message TEXT;
ALTER TABLE system_logs ADD COLUMN IF NOT EXISTS level TEXT DEFAULT 'info';
