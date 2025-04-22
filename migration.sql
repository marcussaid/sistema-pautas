ALTER TABLE registros ADD COLUMN IF NOT EXISTS anexos JSONB DEFAULT '[]'::jsonb;

-- Verifica e adiciona as colunas necessárias na tabela system_logs
DO $$
BEGIN
    -- Verifica se a coluna timestamp existe
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

    -- Verifica se a coluna username existe
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'system_logs'
        AND column_name = 'username'
    ) THEN
        -- Adiciona a coluna username se não existir
        ALTER TABLE system_logs
        ADD COLUMN "username" TEXT;
    END IF;

    -- Verifica se a coluna action existe
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'system_logs'
        AND column_name = 'action'
    ) THEN
        -- Adiciona a coluna action se não existir
        ALTER TABLE system_logs
        ADD COLUMN "action" TEXT;
    END IF;

    -- Verifica se a coluna details existe
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'system_logs'
        AND column_name = 'details'
    ) THEN
        -- Adiciona a coluna details se não existir
        ALTER TABLE system_logs
        ADD COLUMN "details" TEXT;
    END IF;

    -- Verifica se a coluna ip_address existe
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'system_logs'
        AND column_name = 'ip_address'
    ) THEN
        -- Adiciona a coluna ip_address se não existir
        ALTER TABLE system_logs
        ADD COLUMN "ip_address" TEXT;
    END IF;
END
$$;
