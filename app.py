from flask import Flask, render_template, request, redirect, url_for, flash, session, make_response, jsonify, send_from_directory, send_file
import traceback
import os
import json
from werkzeug.utils import secure_filename
from datetime import datetime, date, timedelta
from s3_utils import S3Handler
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import sqlite3
import psycopg2
from psycopg2.extras import DictCursor
from werkzeug.security import generate_password_hash, check_password_hash

# Constantes
STATUS_CHOICES = ['Em andamento', 'Concluído', 'Pendente', 'Cancelado']

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
    if not current_user.is_authenticated:
        return redirect(url_for('login'))
    try:
        if IS_PRODUCTION:
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
            registros = query_db('SELECT * FROM registros ORDER BY data DESC')
            
        return render_template('report.html', registros=registros, status_list=STATUS_CHOICES)
    except Exception as e:
        print(f"[ERROR] Erro ao carregar página inicial: {str(e)}")
        print(f"[ERROR] Traceback: {traceback.format_exc()}")
        flash('Erro ao carregar registros. Por favor, tente novamente.')
        return redirect(url_for('login'))

@app.route('/form')
@login_required
def form():
    print("[INFO] Acessando rota /form")
    today = datetime.now().strftime('%Y-%m-%d')
    return render_template('form.html', today=today, form_data={})

@app.route('/import_csv')
@login_required
def import_csv():
    print("[INFO] Acessando rota /import_csv")
    return render_template('import_csv.html')

@app.route('/export_csv')
@login_required
def export_csv():
    print("[INFO] Iniciando exportação para CSV")
    try:
        # Busca os registros
        if IS_PRODUCTION:
            registros = query_db("""
                SELECT *,
                       TO_CHAR(data, 'YYYY-MM-DD') as data_formatada,
                       TO_CHAR(data_ultima_edicao, 'YYYY-MM-DD HH24:MI:SS') as data_edicao_formatada
                FROM registros 
                ORDER BY data DESC
            """)
            # Ajusta os campos de data
            for registro in registros:
                registro['data'] = registro['data_formatada']
                registro['data_ultima_edicao'] = registro['data_edicao_formatada']
        else:
            registros = query_db('SELECT * FROM registros ORDER BY data DESC')
        
        if not registros:
            flash('Nenhum registro encontrado para exportar.')
            return redirect(url_for('report'))
        
        # Cria o arquivo CSV em memória
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Escreve o cabeçalho
        writer.writerow(['Data', 'Demanda', 'Assunto', 'Local', 'Direcionamentos', 'Status', 'Último Editor', 'Última Edição'])
        
        # Escreve os dados
        for registro in registros:
            writer.writerow([
                registro['data'],
                registro['demanda'],
                registro['assunto'],
                registro['local'],
                registro['direcionamentos'],
                registro['status'],
                registro['ultimo_editor'],
                registro['data_ultima_edicao'] if registro['data_ultima_edicao'] else ''
            ])
        
        # Prepara a resposta
        output.seek(0)
        return Response(
            output.getvalue().encode('utf-8-sig'),
            mimetype='text/csv',
            headers={
                'Content-Disposition': 'attachment; filename=registros.csv',
                'Content-Type': 'text/csv; charset=utf-8'
            }
        )
        
    except Exception as e:
        print(f"[ERROR] Erro ao exportar CSV: {str(e)}")
        print(f"[ERROR] Traceback: {traceback.format_exc()}")
        flash('Erro ao exportar registros. Por favor, tente novamente.')
        return redirect(url_for('report'))

@app.route('/delete_registro/<int:registro_id>', methods=['POST'])
@login_required
def delete_registro(registro_id):
    print(f"[INFO] Tentando excluir registro {registro_id}")
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Primeiro exclui os anexos
        if IS_PRODUCTION:
            # Busca os anexos no S3
            cur.execute('SELECT s3_key FROM anexos WHERE registro_id = %s', [registro_id])
            anexos = cur.fetchall()
            
            # Remove os arquivos do S3
            for anexo in anexos:
                if anexo['s3_key']:
                    try:
                        s3.delete_file(anexo['s3_key'])
                    except Exception as e:
                        print(f"[WARN] Erro ao excluir arquivo do S3: {str(e)}")
            
            # Remove os registros de anexos do banco
            cur.execute('DELETE FROM anexos WHERE registro_id = %s', [registro_id])
            
            # Remove o registro principal
            cur.execute('DELETE FROM registros WHERE id = %s', [registro_id])
        else:
            # Em desenvolvimento, remove os arquivos locais
            cur.execute('SELECT caminho_local FROM anexos WHERE registro_id = ?', [registro_id])
            anexos = cur.fetchall()
            
            # Remove os arquivos locais
            for anexo in anexos:
                if anexo['caminho_local']:
                    try:
                        caminho_completo = os.path.join(app.config['UPLOAD_FOLDER'], anexo['caminho_local'])
                        if os.path.exists(caminho_completo):
                            os.remove(caminho_completo)
                    except Exception as e:
                        print(f"[WARN] Erro ao excluir arquivo local: {str(e)}")
            
            # Remove os registros de anexos do banco
            cur.execute('DELETE FROM anexos WHERE registro_id = ?', [registro_id])
            
            # Remove o registro principal
            cur.execute('DELETE FROM registros WHERE id = ?', [registro_id])
        
        conn.commit()
        print(f"[INFO] Registro {registro_id} excluído com sucesso")
        return jsonify({'success': True})
        
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] Erro ao excluir registro: {str(e)}")
        print(f"[ERROR] Traceback: {traceback.format_exc()}")
        return jsonify({'success': False, 'message': 'Erro ao excluir registro'})
    finally:
        cur.close()
        conn.close()

@app.route('/edit_registro/<int:registro_id>', methods=['GET'])
@login_required
def edit_registro(registro_id):
    print(f"[INFO] Acessando edição do registro {registro_id}")
    try:
        if IS_PRODUCTION:
            registro = query_db("""
                SELECT *,
                       TO_CHAR(data, 'YYYY-MM-DD') as data_formatada,
                       TO_CHAR(data_ultima_edicao, 'YYYY-MM-DD HH24:MI:SS') as data_edicao_formatada
                FROM registros 
                WHERE id = %s
            """, [registro_id], one=True)
            if registro:
                registro['data'] = registro['data_formatada']
                registro['data_ultima_edicao'] = registro['data_edicao_formatada']
        else:
            registro = query_db('SELECT * FROM registros WHERE id = ?', [registro_id], one=True)
            
        if not registro:
            flash('Registro não encontrado.')
            return redirect(url_for('report'))
            
        # Busca anexos
        if IS_PRODUCTION:
            anexos = query_db('SELECT * FROM anexos WHERE registro_id = %s', [registro_id])
        else:
            anexos = query_db('SELECT * FROM anexos WHERE registro_id = ?', [registro_id])
            
        return render_template('edit.html', registro=registro, anexos=anexos, status_list=STATUS_CHOICES)
        
    except Exception as e:
        print(f"[ERROR] Erro ao carregar registro para edição: {str(e)}")
        print(f"[ERROR] Traceback: {traceback.format_exc()}")
        flash('Erro ao carregar registro para edição. Por favor, tente novamente.')
        return redirect(url_for('report'))

@app.route('/submit', methods=['POST'])
@login_required
def submit():
    print("[INFO] Processando submissão de formulário")
    try:
        data = request.form.get('data')
        demanda = request.form.get('demanda')
        assunto = request.form.get('assunto')
        local = request.form.get('local')
        direcionamentos = request.form.get('direcionamentos')
        status = request.form.get('status')
        
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            
            if IS_PRODUCTION:
                cur.execute("""
                    INSERT INTO registros (data, demanda, assunto, local, direcionamentos, status, ultimo_editor)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, [data, demanda, assunto, local, direcionamentos, status, current_user.username])
            else:
                cur.execute("""
                    INSERT INTO registros (data, demanda, assunto, local, direcionamentos, status, ultimo_editor)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    RETURNING id
                """, [data, demanda, assunto, local, direcionamentos, status, current_user.username])
            
            registro_id = cur.fetchone()[0]
            
            # Processa os arquivos anexados
            files = request.files.getlist('files')
            for file in files:
                if file and file.filename:
                    filename = secure_filename(file.filename)
                    if IS_PRODUCTION:
                        # Upload para S3
                        s3_key = f'uploads/{registro_id}/{filename}'
                        s3.upload_fileobj(file, s3_key)
                        
                        # Salva referência no banco
                        cur.execute("""
                            INSERT INTO anexos (registro_id, nome_arquivo, s3_key)
                            VALUES (%s, %s, %s)
                        """, [registro_id, filename, s3_key])
                    else:
                        # Salva localmente
                        upload_path = os.path.join(app.config['UPLOAD_FOLDER'], str(registro_id))
                        os.makedirs(upload_path, exist_ok=True)
                        file.save(os.path.join(upload_path, filename))
                        
                        # Salva referência no banco
                        cur.execute("""
                            INSERT INTO anexos (registro_id, nome_arquivo, caminho_local)
                            VALUES (?, ?, ?)
                        """, [registro_id, filename, os.path.join(str(registro_id), filename)])
            
            conn.commit()
            print(f"[INFO] Registro criado com sucesso. ID: {registro_id}")
            flash('Registro criado com sucesso!')
            return redirect(url_for('report'))
            
        except Exception as e:
            conn.rollback()
            print(f"[ERROR] Erro ao criar registro: {str(e)}")
            print(f"[ERROR] Traceback: {traceback.format_exc()}")
            flash('Erro ao criar registro. Por favor, tente novamente.')
            return render_template('form.html', form_data=request.form, today=datetime.now().strftime('%Y-%m-%d'))
        finally:
            cur.close()
            conn.close()
            
    except Exception as e:
        print(f"[ERROR] Erro ao processar formulário: {str(e)}")
        print(f"[ERROR] Traceback: {traceback.format_exc()}")
        flash('Erro ao processar formulário. Por favor, tente novamente.')
        return render_template('form.html', form_data=request.form, today=datetime.now().strftime('%Y-%m-%d'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    print("[INFO] Acessando rota /register")
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        
        print(f"[INFO] Tentativa de registro para usuário: {username}")
        
        if not all([username, password, confirm_password]):
            print("[ERROR] Campos obrigatórios não preenchidos")
            flash('Por favor, preencha todos os campos.')
            return redirect(url_for('register'))
            
        if password != confirm_password:
            print("[ERROR] Senhas não coincidem")
            flash('As senhas não coincidem.')
            return redirect(url_for('register'))
            
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            
            # Verifica se o usuário já existe
            if IS_PRODUCTION:
                cur.execute('SELECT * FROM users WHERE username = %s', [username])
            else:
                cur.execute('SELECT * FROM users WHERE username = ?', [username])
                
            existing_user = cur.fetchone()
            
            if existing_user:
                print(f"[ERROR] Usuário já existe: {username}")
                flash('Nome de usuário já existe.')
                return redirect(url_for('register'))
                
            # Insere o novo usuário
            if IS_PRODUCTION:
                cur.execute('INSERT INTO users (username, password, is_superuser) VALUES (%s, %s, %s)',
                          [username, password, False])
            else:
                cur.execute('INSERT INTO users (username, password, is_superuser) VALUES (?, ?, ?)',
                          [username, password, False])
                
            conn.commit()
            print(f"[INFO] Usuário criado com sucesso: {username}")
            flash('Usuário criado com sucesso!')
            return redirect(url_for('login'))
            
        except Exception as e:
            print(f"[ERROR] Erro ao criar usuário: {str(e)}")
            print(f"[ERROR] Traceback: {traceback.format_exc()}")
            flash('Erro ao criar usuário. Por favor, tente novamente.')
            return redirect(url_for('register'))
        finally:
            cur.close()
            conn.close()
            
    return render_template('register.html')

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

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    print("[INFO] Acessando rota /forgot_password")
    try:
        if request.method == 'POST':
            username = request.form.get('username', '').strip()
            print(f"[INFO] Tentativa de recuperação de senha para usuário: {username}")
            
            if not username:
                print("[ERROR] Nome de usuário não fornecido")
                flash('Por favor, informe o nome de usuário.')
                return redirect(url_for('forgot_password'))
            
            conn = get_db_connection()
            try:
                cur = conn.cursor()
                
                # Adapta a query para PostgreSQL se estiver em produção
                if IS_PRODUCTION:
                    cur.execute('SELECT * FROM users WHERE username = %s', [username])
                else:
                    cur.execute('SELECT * FROM users WHERE username = ?', [username])
                
                user = cur.fetchone()
                
                if not user:
                    print(f"[ERROR] Usuário não encontrado: {username}")
                    flash('Usuário não encontrado.')
                    return redirect(url_for('forgot_password'))
                
                # Em um sistema real, aqui seria enviado um e-mail com link de redefinição
                # Como é uma versão simplificada, apenas resetamos para uma senha padrão
                if IS_PRODUCTION:
                    cur.execute('UPDATE users SET password = %s WHERE id = %s', ['123456', user['id']])
                else:
                    cur.execute('UPDATE users SET password = ? WHERE id = ?', ['123456', user['id']])
                
                conn.commit()
                print(f"[INFO] Senha redefinida com sucesso para usuário: {username}")
                flash('Senha redefinida para: 123456. Por favor, altere sua senha após o login.')
                return redirect(url_for('login'))
            finally:
                cur.close()
                conn.close()
                
    except Exception as e:
        print(f"[ERROR] Erro ao processar recuperação de senha: {str(e)}")
        print(f"[ERROR] Traceback: {traceback.format_exc()}")
        flash('Erro ao processar a recuperação de senha. Por favor, tente novamente.')
        return redirect(url_for('forgot_password'))
            
    return render_template('forgot_password.html')

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
