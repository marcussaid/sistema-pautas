import sqlite3

def fix_system_logs():
    try:
        # Conectar ao banco SQLite
        conn = sqlite3.connect('sistema_demandas.db')
        cur = conn.cursor()
        
        # Adicionar as colunas necessárias
        try:
            cur.execute('ALTER TABLE system_logs ADD COLUMN message TEXT')
            print("Coluna 'message' adicionada com sucesso")
        except:
            print("Coluna 'message' já existe")
            
        try:
            cur.execute('ALTER TABLE system_logs ADD COLUMN level TEXT DEFAULT "info"')
            print("Coluna 'level' adicionada com sucesso")
        except:
            print("Coluna 'level' já existe")
            
        # Atualizar registros existentes
        cur.execute('''
            UPDATE system_logs 
            SET message = action || ': ' || details,
                level = 'info'
            WHERE message IS NULL
        ''')
        
        conn.commit()
        print("Registros atualizados com sucesso")
        
    except Exception as e:
        print(f"Erro: {str(e)}")
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    fix_system_logs()
