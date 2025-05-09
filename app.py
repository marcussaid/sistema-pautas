from flask import Flask, render_template, request, redirect, url_for, flash, session, make_response, jsonify, send_from_directory, send_file
import traceback
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
app = Flask(__name__, static_folder='static', static_url_path='/static')
app.secret_key = os.environ.get('SECRET_KEY', 'sistema_demandas_secret_key_2024')

# Detecta o ambiente (development vs. production)
IS_PRODUCTION = os.environ.get('RENDER', 'false').lower() == 'true'

# Configuração do banco de dados
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://sistema_demandas_db_user:cP52Pdxr3o1tuCVk5TVs9B6MW5rEF6UR@dpg-cvuif46mcj7s73cetkrg-a/sistema_demandas_db')
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

# Configuração do Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.unauthorized_handler
def unauthorized():
    print("[ERROR] Acesso não autorizado detectado")
    print(f"[INFO] URL atual: {request.url}")
    print(f"[INFO] Método: {request.method}")
    flash('Por favor, faça login para acessar esta página.')
    return redirect(url_for('login'))

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
    print(f"[INFO] Tentando carregar usuário com ID: {user_id}")
    try:
        user = query_db('SELECT * FROM users WHERE id = ?', [user_id], one=True)
        if not user:
            print(f"[ERROR] Usuário não encontrado com ID: {user_id}")
            return None
        print(f"[INFO] Usuário carregado com sucesso: {user['username']}")
        return User(user['id'], user['username'], user['is_superuser'])
    except Exception as e:
        print(f"[ERROR] Erro ao carregar usuário: {str(e)}")
        print(f"[ERROR] Traceback: {traceback.format_exc()}")
        return None

# Função para conexão com banco de dados
def get_db_connection():
    print("[INFO] Iniciando conexão com o banco de dados")
    print(f"[INFO] Ambiente de produção: {IS_PRODUCTION}")
    
    try:
        if IS_PRODUCTION:
            print("[INFO] Conectando ao PostgreSQL...")
            conn = psycopg2.connect(DATABASE_URL)
            conn.cursor_factory = DictCursor
            print("[INFO] Conexão PostgreSQL estabelecida com sucesso")
            return conn
        else:
            print("[INFO] Conectando ao SQLite...")
            conn = sqlite3.connect('database.db')
            conn.row_factory = sqlite3.Row
            print("[INFO] Conexão SQLite estabelecida com sucesso")
            return conn
    except Exception as e:
        print(f"[ERROR] Erro ao conectar ao banco de dados: {str(e)}")
        print(f"[ERROR] Traceback: {traceback.format_exc()}")
        raise

# Função para consulta ao banco de dados
def query_db(query, args=(), one=False):
    print(f"[INFO] Executando query: {query}")
    print(f"[INFO] Argumentos: {args}")
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Adapta a query para PostgreSQL se estiver em produção
        if IS_PRODUCTION:
            query = query.replace('?', '%s')
        
        cur.execute(query, args)
        rv = cur.fetchall()
        print(f"[INFO] Query executada com sucesso. Resultados: {len(rv) if rv else 0}")
        cur.close()
        conn.close()
        return (rv[0] if rv else None) if one else rv
    except Exception as e:
        print(f"[ERROR] Erro ao executar query: {str(e)}")
        print(f"[ERROR] Traceback: {traceback.format_exc()}")
        raise

# Configuração de uploads
if IS_PRODUCTION:
    s3 = S3Handler()
    print("[INFO] Ambiente de produção detectado. Usando AWS S3 para uploads.")
else:
    app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'uploads')
    print(f"[INFO] Ambiente de desenvolvimento detectado. Diretório de uploads: {app.config['UPLOAD_FOLDER']}")
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('form'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    print("[INFO] Acessando rota /login")
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        print(f"[INFO] Tentativa de login para usuário: {username}")
        
        try:
            user = query_db('SELECT * FROM users WHERE username = ? AND password = ?',
                          [username, password], one=True)
            if user:
                print(f"[INFO] Usuário {username} encontrado, criando objeto User")
                user_obj = User(user['id'], user['username'], user['is_superuser'])
                login_user(user_obj)
                print(f"[INFO] Login realizado com sucesso. ID: {user_obj.id}, is_superuser: {user_obj.is_superuser}")
                return redirect(url_for('form'))
            else:
                print(f"[ERROR] Usuário ou senha inválidos para: {username}")
                flash('Usuário ou senha inválidos.')
        except Exception as e:
            print(f"[ERROR] Erro durante o login: {str(e)}")
            print(f"[ERROR] Traceback: {traceback.format_exc()}")
            flash('Erro ao realizar login. Por favor, tente novamente.')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/admin')
@login_required
def admin():
    print("[INFO] Acessando rota /admin")
    print(f"[INFO] current_user: {current_user}, is_authenticated: {current_user.is_authenticated}")
    
    try:
        if not hasattr(current_user, 'is_superuser') or not current_user.is_superuser:
            print("[ERROR] Usuário não é superusuário")
            flash('Acesso negado: você não tem permissão para acessar essa página.')
            return redirect(url_for('form'))
            
        if IS_PRODUCTION:
            users = query_db('SELECT * FROM users ORDER BY username')
            registros = query_db("""
                SELECT *,
                       TO_CHAR(data, 'YYYY-MM-DD') as data_formatada,
                       TO_CHAR(data_ultima_edicao, 'YYYY-MM-DD HH24:MI:SS') as data_edicao_formatada
                FROM registros 
                ORDER BY data DESC
            """)
            # Ajusta os campos de data para o formato correto
            for registro in registros:
                registro['data'] = registro['data_formatada']
                registro['data_ultima_edicao'] = registro['data_edicao_formatada']
        else:
            users = query_db('SELECT * FROM users ORDER BY username')
            registros = query_db('SELECT * FROM registros ORDER BY data DESC')
            
        return render_template('admin.html', users=users, registros=registros)
    except Exception as e:
        print(f"[ERROR] Erro na rota admin: {str(e)}")
        print(f"[ERROR] Traceback: {traceback.format_exc()}")
        flash('Erro ao carregar página de administração.')
        return redirect(url_for('form'))

@app.route('/report')
@login_required
def report():
    print("[INFO] Acessando rota /report")
    if not current_user.is_authenticated:
        print("[ERROR] Usuário não autenticado")
        return redirect(url_for('login'))
        
    try:
        print("[INFO] Usuário autenticado, iniciando carregamento do relatório...")
        
        # Busca todos os registros ordenados por data (mais recentes primeiro)
        print("[DEBUG] Executando query para buscar registros...")
        if IS_PRODUCTION:
            registros = query_db("""
                SELECT *, 
                       TO_CHAR(data, 'YYYY-MM-DD') as data_formatada,
                       TO_CHAR(data_ultima_edicao, 'YYYY-MM-DD HH24:MI:SS') as data_edicao_formatada
                FROM registros
                ORDER BY data DESC, id DESC
            """)
            # Ajusta os campos de data para o formato correto
            for registro in registros:
                registro['data'] = registro['data_formatada']
                registro['data_ultima_edicao'] = registro['data_edicao_formatada']
        else:
            registros = query_db("""
                SELECT * FROM registros
                ORDER BY data DESC, id DESC
            """)
            
        return render_template('report.html', registros=registros, status_list=STATUS_CHOICES)
    except Exception as e:
        print(f"[DEBUG] Erro ao carregar relatório: {str(e)}")
        print(f"[DEBUG] Traceback completo: {traceback.format_exc()}")
        flash('Erro ao carregar o relatório. Por favor, tente novamente.')
        return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
