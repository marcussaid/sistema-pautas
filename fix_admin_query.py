import sqlite3

def fix_admin_query():
    try:
        # Conectar ao banco SQLite
        conn = sqlite3.connect('sistema_demandas.db')
        cur = conn.cursor()
        
        # Criar uma view temporária para os logs
        cur.execute('''
            CREATE VIEW IF NOT EXISTS system_logs_view AS
            SELECT 
                id,
                timestamp,
                username,
                action,
                details,
                ip_address,
                message,
                level,
                timestamp as created_at
            FROM system_logs
        ''')
        
        conn.commit()
        print("View criada com sucesso")
        
    except Exception as e:
        print(f"Erro: {str(e)}")
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    fix_admin_query()
