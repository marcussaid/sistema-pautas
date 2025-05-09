import sqlite3

def fix_logs():
    try:
        # Conectar ao banco SQLite
        conn = sqlite3.connect('sistema_demandas.db')
        cur = conn.cursor()
        
        # Adicionar a coluna created_at se não existir
        try:
            cur.execute('ALTER TABLE system_logs ADD COLUMN created_at TIMESTAMP')
            print("Coluna created_at adicionada com sucesso")
        except:
            print("Coluna created_at já existe")
        
        # Atualizar created_at com o valor de timestamp
        cur.execute('''
            UPDATE system_logs 
            SET created_at = timestamp
            WHERE created_at IS NULL
        ''')
        
        conn.commit()
        print("Registros atualizados com sucesso")
        
    except Exception as e:
        print(f"Erro: {str(e)}")
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    fix_logs()
