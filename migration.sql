ALTER TABLE registros ADD COLUMN IF NOT EXISTS anexos JSONB DEFAULT '[]'::jsonb;

-- Verifica se a coluna timestamp existe
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'system_logs'
        AND column_name = 'timestamp'
    ) THEN
        -- Adiciona a coluna timestamp se não existir
        ALTER TABLE system_logs
        ADD COLUMN "timestamp" TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;
    END IF;
END
$$;
