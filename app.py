from flask import Flask, render_template, request, redirect, url_for, flash, session, make_response, jsonify, send_from_directory, send_file, Response
import traceback
import os
import json
import io
import csv
from werkzeug.utils import secure_filename
from datetime import datetime, date, timedelta
from s3_utils_new import S3Handler
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import psycopg2
from psycopg2.extras import DictCursor
from werkzeug.security import generate_password_hash, check_password_hash

# Constantes
STATUS_CHOICES = ['Em andamento', 'Concluído', 'Pendente', 'Cancelado']

# Inicialização do Flask
app = Flask(__name__, static_folder='static', static_url_path='/static')
app.secret_key = os.environ.get('SECRET_KEY', 'sistema_demandas_secret_key_2024')

# Verificar ambiente de produção
IS_PRODUCTION = os.environ.get('RENDER', 'false').lower() == 'true'
if not IS_PRODUCTION:
    raise Exception("Este sistema deve ser executado apenas em ambiente de produção")

# Inicializar S3
try:
    s3 = S3Handler()
    print("[INFO] S3Handler inicializado com sucesso")
except Exception as e:
    print(f"[FATAL] Erro ao inicializar S3Handler: {str(e)}")
    raise

# Configuração do banco de dados
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

# Configuração do Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.unauthorized_handler
def unauthorized():
    print("[ERROR] Acesso não autorizado detectado")
    flash('Por favor, faça login para acessar esta página.')
    return redirect(url_for('login'))

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
    try:
        user = query_db('SELECT * FROM users WHERE id = %s', [user_id], one=True)
        if user:
            return User(user['id'], user['username'], user['is_superuser'])
        return None
    except Exception as e:
        print(f"[ERROR] Erro ao carregar usuário: {str(e)}")
        return None

def get_db_connection():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        conn.cursor_factory = DictCursor
        return conn
    except Exception as e:
        print(f"[ERROR] Erro ao conectar ao banco de dados: {str(e)}")
        raise

def query_db(query, args=(), one=False):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(query, args)
        rv = cur.fetchall()
        cur.close()
        conn.close()
        return (rv[0] if rv else None) if one else rv
    except Exception as e:
        print(f"[ERROR] Erro ao executar query: {str(e)}")
        raise

@app.route('/')
def index():
    if not current_user.is_authenticated:
        return redirect(url_for('login'))
    try:
        registros = query_db("""
            SELECT *,
                   TO_CHAR(data, 'YYYY-MM-DD') as data_formatada,
                   TO_CHAR(data_ultima_edicao, 'YYYY-MM-DD HH24:MI:SS') as data_edicao_formatada
            FROM registros 
            ORDER BY data DESC
        """)
        for registro in registros:
            registro['data'] = registro['data_formatada']
            registro['data_ultima_edicao'] = registro['data_edicao_formatada']
        return render_template('report.html', registros=registros, status_list=STATUS_CHOICES)
    except Exception as e:
        print(f"[ERROR] Erro ao carregar página inicial: {str(e)}")
        flash('Erro ao carregar registros. Por favor, tente novamente.')
        return redirect(url_for('login'))

@app.route('/submit', methods=['POST'])
@login_required
def submit():
    try:
        data = request.form.get('data')
        demanda = request.form.get('demanda')
        assunto = request.form.get('assunto')
        local = request.form.get('local')
        direcionamentos = request.form.get('direcionamentos')
        status = request.form.get('status')
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            # Inserir registro
            cur.execute("""
                INSERT INTO registros (data, demanda, assunto, local, direcionamentos, status, ultimo_editor)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, [data, demanda, assunto, local, direcionamentos, status, current_user.username])
            
            registro_id = cur.fetchone()[0]
            
            # Processar anexos
            files = request.files.getlist('files')
            for file in files:
                if file and file.filename:
                    try:
                        # Upload para S3
                        result = s3.process_upload(file, f'uploads/{registro_id}/')
                        if result['success']:
                            # Salvar referência no banco
                            cur.execute("""
                                INSERT INTO anexos (registro_id, nome_arquivo, s3_key)
                                VALUES (%s, %s, %s)
                            """, [registro_id, result['original_name'], result['s3_key']])
                        else:
                            raise Exception(f"Erro no upload: {result['error']}")
                    except Exception as e:
                        print(f"[ERROR] Erro ao processar anexo: {str(e)}")
                        raise
            
            conn.commit()
            flash('Registro criado com sucesso!')
            return redirect(url_for('report'))
            
        except Exception as e:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()
            
    except Exception as e:
        print(f"[ERROR] Erro ao processar formulário: {str(e)}")
        flash('Erro ao criar registro. Por favor, tente novamente.')
        return render_template('form.html', form_data=request.form)

@app.route('/delete_registro/<int:registro_id>', methods=['POST'])
@login_required
def delete_registro(registro_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            # Buscar anexos no S3
            cur.execute('SELECT s3_key FROM anexos WHERE registro_id = %s', [registro_id])
            anexos = cur.fetchall()
            
            # Remover arquivos do S3
            for anexo in anexos:
                if anexo['s3_key']:
                    if not s3.delete_file(anexo['s3_key']):
                        print(f"[WARN] Erro ao excluir arquivo do S3: {anexo['s3_key']}")
            
            # Remover registros do banco
            cur.execute('DELETE FROM anexos WHERE registro_id = %s', [registro_id])
            cur.execute('DELETE FROM registros WHERE id = %s', [registro_id])
            
            conn.commit()
            return jsonify({'success': True})
            
        except Exception as e:
            conn.rollback()
            raise
        finally:
            cur.close()
            conn.close()
            
    except Exception as e:
        print(f"[ERROR] Erro ao excluir registro: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/edit_registro/<int:registro_id>', methods=['GET', 'POST'])
@login_required
def edit_registro(registro_id):
    try:
        if request.method == 'POST':
            conn = get_db_connection()
            cur = conn.cursor()
            
            try:
                # Atualizar registro
                cur.execute("""
                    UPDATE registros 
                    SET data = %s, demanda = %s, assunto = %s, local = %s, 
                        direcionamentos = %s, status = %s, 
                        ultimo_editor = %s, data_ultima_edicao = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, [
                    request.form['data'],
                    request.form['demanda'],
                    request.form['assunto'],
                    request.form['local'],
                    request.form['direcionamentos'],
                    request.form['status'],
                    current_user.username,
                    registro_id
                ])
                
                # Processar novos anexos
                files = request.files.getlist('files')
                for file in files:
                    if file and file.filename:
                        result = s3.process_upload(file, f'uploads/{registro_id}/')
                        if result['success']:
                            cur.execute("""
                                INSERT INTO anexos (registro_id, nome_arquivo, s3_key)
                                VALUES (%s, %s, %s)
                            """, [registro_id, result['original_name'], result['s3_key']])
                
                conn.commit()
                flash('Registro atualizado com sucesso!')
                return redirect(url_for('report'))
                
            except Exception as e:
                conn.rollback()
                raise
            finally:
                cur.close()
                conn.close()
        else:
            # GET request - mostrar formulário de edição
            registro = query_db("""
                SELECT *,
                       TO_CHAR(data, 'YYYY-MM-DD') as data_formatada,
                       TO_CHAR(data_ultima_edicao, 'YYYY-MM-DD HH24:MI:SS') as data_edicao_formatada
                FROM registros 
                WHERE id = %s
            """, [registro_id], one=True)
            
            if not registro:
                flash('Registro não encontrado.')
                return redirect(url_for('report'))
            
            registro['data'] = registro['data_formatada']
            registro['data_ultima_edicao'] = registro['data_edicao_formatada']
            
            anexos = query_db('SELECT * FROM anexos WHERE registro_id = %s', [registro_id])
            return render_template('edit.html', registro=registro, anexos=anexos, status_list=STATUS_CHOICES)
            
    except Exception as e:
        print(f"[ERROR] Erro ao processar edição: {str(e)}")
        flash('Erro ao processar edição. Por favor, tente novamente.')
        return redirect(url_for('report'))

if __name__ == '__main__':
    app.run(debug=False)
