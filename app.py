import os
import json
import io
import csv
import traceback
import psycopg2
from psycopg2.extras import DictCursor
from werkzeug.utils import secure_filename
from datetime import datetime, date, timedelta
from s3_utils import S3Handler  # Import correto
from flask import Flask, render_template, request, redirect, url_for, flash, session, make_response, jsonify, send_from_directory, send_file, Response
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user

print("Starting Flask app - version 2024-06-01")  # Unique log to confirm deployed version

# Função para conexão com banco de dados
def get_db_connection():
    DATABASE_URL = os.environ.get('DATABASE_URL')
    if DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
    conn = psycopg2.connect(DATABASE_URL)
    conn.cursor_factory = DictCursor
    return conn

# Inicialização do Flask
app = Flask(__name__, static_folder='static', static_url_path='/static')
app.secret_key = os.environ.get('SECRET_KEY', 'sistema_demandas_secret_key_2024')

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id, username, password, is_superuser):
        self.id = id
        self.username = username
        self.password = password
        self.is_superuser = is_superuser

@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, username, password, is_superuser FROM users WHERE id = %s", (user_id,))
    user_data = cur.fetchone()
    cur.close()
    conn.close()
    if user_data:
        return User(*user_data)
    return None

@app.context_processor
def inject_user():
    return dict(current_user=current_user)

def init_db():
    """Inicializa o banco de dados com tabelas e usuário admin"""
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Criar tabela de usuários se não existir
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(255) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                is_superuser BOOLEAN DEFAULT FALSE
            )
        """)
        
        # Criar tabela de registros se não existir
        cur.execute("""
            CREATE TABLE IF NOT EXISTS registros (
                id SERIAL PRIMARY KEY,
                data DATE NOT NULL,
                demanda TEXT NOT NULL,
                assunto TEXT,
                local TEXT,
                direcionamentos TEXT,
                status VARCHAR(50) NOT NULL DEFAULT 'Pendente',
                ultimo_editor VARCHAR(255),
                data_ultima_edicao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (ultimo_editor) REFERENCES users(username)
            )
        """)
        
        # Criar tabela de anexos se não existir
        cur.execute("""
            CREATE TABLE IF NOT EXISTS anexos (
                id SERIAL PRIMARY KEY,
                registro_id INTEGER NOT NULL,
                nome_arquivo VARCHAR(255) NOT NULL,
                s3_key VARCHAR(255),
                data_upload TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (registro_id) REFERENCES registros(id) ON DELETE CASCADE
            )
        """)
        
        # Verificar se existe algum usuário admin
        cur.execute("SELECT COUNT(*) FROM users WHERE is_superuser = true")
        admin_count = cur.fetchone()[0]
        
        if admin_count == 0:
            # Criar usuário admin padrão
            cur.execute("""
                INSERT INTO users (username, password, is_superuser)
                VALUES (%s, %s, %s)
            """, ['admin', 'admin123', True])
            print("[INFO] Usuário admin criado com sucesso")
        
        conn.commit()
        print("[INFO] Banco de dados inicializado com sucesso")
        
    except Exception as e:
        print(f"[ERROR] Erro ao inicializar banco de dados: {str(e)}")
        print(f"[ERROR] Traceback: {traceback.format_exc()}")
        if conn:
            conn.rollback()
        raise
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

# Inicializar banco de dados
init_db()

# Tratamento global de erros para logar exceções detalhadas
import logging
from flask import got_request_exception

def log_exception(sender, exception, **extra):
    sender.logger.error(f"Exception: {exception}", exc_info=exception)

got_request_exception.connect(log_exception, app)

@app.route('/')
def home():
    return render_template('home.html')

# Implementação das rotas para as páginas do sistema

@app.route('/admin')
@login_required
def admin():
    return render_template('admin.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Lógica de autenticação aqui
        return redirect(url_for('home'))
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Lógica de registro aqui
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/report')
@login_required
def report():
    return render_template('report.html')

@app.route('/import_csv', methods=['GET', 'POST'])
@login_required
def import_csv():
    if request.method == 'POST':
        # Lógica para importar CSV
        return redirect(url_for('report'))
    return render_template('import_csv.html')

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        # Lógica para recuperação de senha
        return redirect(url_for('login'))
    return render_template('forgot_password.html')

# Adicione outras rotas conforme necessário para as páginas restantes
