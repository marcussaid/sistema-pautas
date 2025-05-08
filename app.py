from flask import Flask, render_template, request, redirect, url_for, flash, session, make_response, jsonify, send_from_directory, send_file
import os
import json
from werkzeug.utils import secure_filename
from datetime import datetime, date
from s3_utils import S3Handler
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import sqlite3
import psycopg2
from psycopg2.extras import DictCursor

# Inicialização do Flask
app = Flask(__name__, static_folder='static')
app.secret_key = os.environ.get('SECRET_KEY', 'sistema_demandas_secret_key_2024')

# Detecta o ambiente (development vs. production)
IS_PRODUCTION = os.environ.get('RENDER', False)

# Configuração de uploads
if IS_PRODUCTION:
    # No Render, use S3
    s3 = S3Handler()
    print("[INFO] Ambiente de produção detectado. Usando AWS S3 para uploads.")
else:
    # Em desenvolvimento local, use o diretório da aplicação
    app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'uploads')
    print(f"[INFO] Ambiente de desenvolvimento detectado. Diretório de uploads: {app.config['UPLOAD_FOLDER']}")
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Configuração do Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Configuração do banco de dados
if IS_PRODUCTION:
    # Configuração para PostgreSQL no ambiente de produção (Render)
    DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://sistema_demandas_db_user:cP52Pdxr3o1tuCVk5TVs9B6MW5rEF6UR@dpg-cvuif46mcj7s73cetkrg-a/sistema_demandas_db')
    # Se o DATABASE_URL começa com postgres://, atualize para postgresql://
    if DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
else:
    # Configuração para SQLite no ambiente de desenvolvimento
    DATABASE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sistema_demandas.db')

# Status padrão
STATUS_CHOICES = ['Em andamento', 'Concluído', 'Pendente', 'Cancelado']

# Classe User para o Flask-Login
class User(UserMixin):
    def __init__(self, id, username, is_superuser=False):
        self.id = id
        self.username = username
        self.is_superuser = is_superuser

    def get_id(self):
        return str(self.id)

@login_manager.user_loader
def load_user(user_id):
    user = query_db('SELECT * FROM users WHERE id = ?', [user_id], one=True)
    if not user:
        return None
    return User(user['id'], user['username'], user['is_superuser'])

# Função para conexão com banco de dados
def get_db_connection():
    if IS_PRODUCTION:
        # Conectar ao PostgreSQL
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = False
        return conn
    else:
        # Conectar ao SQLite
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        return conn

# Função para consulta ao banco de dados
def query_db(query, args=(), one=False):
    try:
        conn = get_db_connection()
        
        if IS_PRODUCTION:
            # PostgreSQL
            cur = conn.cursor(cursor_factory=DictCursor)
            # Adapta os placeholders do SQLite (?) para PostgreSQL (%s)
            query = query.replace('?', '%s')
        else:
            # SQLite
            cur = conn.cursor()
            # Se a consulta contém %s (placeholder do PostgreSQL), mude para ? (placeholder do SQLite)
            query = query.replace('%s', '?')
        
        cur.execute(query, args)
        
        if query.strip().upper().startswith(('INSERT', 'UPDATE', 'DELETE', 'CREATE', 'ALTER', 'DROP')):
            conn.commit()
            rv = cur.rowcount
        else:
            if IS_PRODUCTION:
                # PostgreSQL já retorna os resultados como dicionários com DictCursor
                rv = [dict(row) for row in cur.fetchall()]
            else:
                # SQLite precisa ser convertido para dicionário
                rv = [dict(zip([column[0] for column in cur.description], row)) for row in cur.fetchall()]
            
        cur.close()
        conn.close()
        
        return (rv[0] if rv else None) if one else rv
    except Exception as e:
        print(f"Erro na consulta ao banco de dados: {str(e)}")
        if 'conn' in locals() and conn is not None:
            conn.close()
        raise e

# ... (previous code remains the same) ...

@app.route('/report')
@login_required
def report():
    try:
        # Busca todos os registros ordenados por data (mais recentes primeiro)
        registros = query_db('''
            SELECT * FROM registros
            ORDER BY data DESC, id DESC
        ''')
        
        # Processa os anexos de cada registro
        for registro in registros:
            try:
                if 'anexos' in registro and registro['anexos']:
                    # Se for string (SQLite), converte para JSON
                    if isinstance(registro['anexos'], str):
                        try:
                            registro['anexos'] = json.loads(registro['anexos'])
                        except json.JSONDecodeError:
                            print(f"Erro ao decodificar JSON dos anexos do registro {registro.get('id')}")
                            registro['anexos'] = []
                    # Se já for um objeto (PostgreSQL JSONB), mantém como está
                    elif not isinstance(registro['anexos'], list):
                        registro['anexos'] = []
                else:
                    registro['anexos'] = []
            except Exception as e:
                print(f"Erro ao processar anexos do registro {registro.get('id')}: {str(e)}")
                registro['anexos'] = []
        
        return render_template('report.html', registros=registros, status_list=STATUS_CHOICES)
    except Exception as e:
        print(f"Erro ao carregar relatório: {str(e)}")
        flash('Erro ao carregar o relatório. Por favor, tente novamente.')
        return redirect(url_for('index'))

# ... (rest of the code remains the same) ...

if __name__ == '__main__':
    # Garantir que as tabelas do banco de dados existam
    ensure_tables()
    # Iniciar o servidor Flask
    app.run(debug=True, host='0.0.0.0', port=8000)
