from flask import Flask, render_template, request, redirect, url_for, flash, session, make_response, jsonify, send_from_directory, send_file, Response
import traceback
import os
import json
import io
import csv
import traceback
from werkzeug.utils import secure_filename
from datetime import datetime, date, timedelta
from s3_utils import S3Handler  # Import correto
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import psycopg2
from psycopg2.extras import DictCursor
from werkzeug.security import generate_password_hash, check_password_hash

# Constantes
STATUS_CHOICES = ['Em andamento', 'Concluído', 'Pendente', 'Cancelado']

# Inicialização do Flask
app = Flask(__name__, static_folder='static', static_url_path='/static')
app.secret_key = os.environ.get('SECRET_KEY', 'sistema_demandas_secret_key_2024')

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

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        try:
            # Primeiro, verificar se o usuário existe
            user = query_db('SELECT * FROM users WHERE username = %s', [username], one=True)
            if user:
                print(f"[INFO] Usuário encontrado: {username}")
                # Se o usuário existe, verificar a senha
                if user['password'] == password:  # Em produção, usar hash da senha
                    user_obj = User(user['id'], user['username'], user['is_superuser'])
                    login_user(user_obj)
                    print(f"[INFO] Login bem-sucedido para: {username}")
                    return redirect(url_for('report'))
                else:
                    print(f"[INFO] Senha incorreta para usuário: {username}")
                    flash('Usuário ou senha inválidos.')
            else:
                print(f"[INFO] Usuário não encontrado: {username}")
                flash('Usuário ou senha inválidos.')
        except Exception as e:
            print(f"[ERROR] Erro durante o login: {str(e)}")
            print(f"[ERROR] Traceback: {traceback.format_exc()}")
            flash('Erro ao realizar login. Por favor, tente novamente.')
    return render_template('login.html')

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        username = request.form.get('username')
        try:
            user = query_db('SELECT * FROM users WHERE username = %s', [username], one=True)
            if user:
                # TODO: Implementar lógica de recuperação de senha
                flash('Instruções para redefinir sua senha foram enviadas.')
            else:
                flash('Se o usuário existir em nossa base, você receberá instruções para redefinir sua senha.')
            return redirect(url_for('login'))
        except Exception as e:
            print(f"[ERROR] Erro ao processar recuperação de senha: {str(e)}")
            flash('Erro ao processar solicitação. Por favor, tente novamente.')
    return render_template('forgot_password.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        try:
            # Verificar se usuário já existe
            existing_user = query_db('SELECT * FROM users WHERE username = %s', [username], one=True)
            if existing_user:
                flash('Nome de usuário já existe.')
                return redirect(url_for('register'))
            
            # Criar novo usuário
            conn = get_db_connection()
            cur = conn.cursor()
            try:
                cur.execute(
                    'INSERT INTO users (username, password, is_superuser) VALUES (%s, %s, %s)',
                    [username, password, False]
                )
                conn.commit()
                flash('Conta criada com sucesso! Faça login para continuar.')
                return redirect(url_for('login'))
            finally:
                cur.close()
                conn.close()
                
        except Exception as e:
            print(f"[ERROR] Erro ao criar usuário: {str(e)}")
            flash('Erro ao criar conta. Por favor, tente novamente.')
            return redirect(url_for('register'))
            
    return render_template('register.html')

@app.route('/admin')
@login_required
def admin():
    if not current_user.is_superuser:
        flash('Acesso negado. Você não tem permissão para acessar esta página.')
        return redirect(url_for('index'))
    try:
        users = query_db('SELECT * FROM users ORDER BY username')
        
        # Estatísticas
        stats = {
            'total_registros': query_db('SELECT COUNT(*) as count FROM registros', one=True)['count'],
            'registros_hoje': query_db("""
                SELECT COUNT(*) as count FROM registros 
                WHERE DATE(data) = CURRENT_DATE
            """, one=True)['count'],
            'total_usuarios': len(users),
            'registros_pendentes': query_db("""
                SELECT COUNT(*) as count FROM registros 
                WHERE status = 'Pendente'
            """, one=True)['count'],
            'status_counts': {}
        }
        
        # Contagem por status
        status_counts = query_db('SELECT status, COUNT(*) as count FROM registros GROUP BY status')
        stats['status_counts'] = {row['status']: row['count'] for row in status_counts}
        
        # Configurações do sistema
        settings = {
            'per_page': 10,  # Valor padrão
            'session_timeout': 30,  # 30 minutos
            'auto_backup': 'daily'
        }
        
        return render_template('admin.html', users=users, stats=stats, settings=settings)
    except Exception as e:
        print(f"[ERROR] Erro ao carregar página de admin: {str(e)}")
        flash('Erro ao carregar página de administração.')
        return redirect(url_for('index'))

@app.route('/admin/user/<int:user_id>', methods=['PUT'])
@login_required
def update_user(user_id):
    if not current_user.is_superuser:
        return jsonify({'error': 'Acesso negado'}), 403
    
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        is_superuser = data.get('is_superuser', False)
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            if password:
                cur.execute("""
                    UPDATE users 
                    SET username = %s, password = %s, is_superuser = %s 
                    WHERE id = %s
                """, [username, password, is_superuser, user_id])
            else:
                cur.execute("""
                    UPDATE users 
                    SET username = %s, is_superuser = %s 
                    WHERE id = %s
                """, [username, is_superuser, user_id])
            
            conn.commit()
            return jsonify({'success': True})
            
        finally:
            cur.close()
            conn.close()
            
    except Exception as e:
        print(f"[ERROR] Erro ao atualizar usuário: {str(e)}")
        return jsonify({'error': 'Erro ao atualizar usuário'}), 500

@app.route('/delete_user/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    if not current_user.is_superuser:
        flash('Acesso negado')
        return redirect(url_for('admin'))
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            # Não permitir excluir o próprio usuário
            if user_id == current_user.id:
                flash('Você não pode excluir seu próprio usuário')
                return redirect(url_for('admin'))
            
            cur.execute('DELETE FROM users WHERE id = %s', [user_id])
            conn.commit()
            flash('Usuário excluído com sucesso')
            
        finally:
            cur.close()
            conn.close()
            
    except Exception as e:
        print(f"[ERROR] Erro ao excluir usuário: {str(e)}")
        flash('Erro ao excluir usuário')
        
    return redirect(url_for('admin'))

@app.route('/export_csv')
@login_required
def export_csv():
    if not current_user.is_superuser:
        flash('Acesso negado')
        return redirect(url_for('admin'))
    
    try:
        registros = query_db("""
            SELECT r.*, a.nome_arquivo, a.s3_key
            FROM registros r
            LEFT JOIN anexos a ON r.id = a.registro_id
            ORDER BY r.data DESC, r.id DESC
        """)
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Cabeçalho
        writer.writerow(['ID', 'Data', 'Demanda', 'Assunto', 'Local', 'Direcionamentos', 
                        'Status', 'Último Editor', 'Data Última Edição', 'Anexos'])
        
        # Dados
        for registro in registros:
            writer.writerow([
                registro['id'],
                registro['data'].strftime('%Y-%m-%d'),
                registro['demanda'],
                registro['assunto'],
                registro['local'],
                registro['direcionamentos'],
                registro['status'],
                registro['ultimo_editor'],
                registro['data_ultima_edicao'].strftime('%Y-%m-%d %H:%M:%S') if registro['data_ultima_edicao'] else '',
                registro['nome_arquivo'] if registro['nome_arquivo'] else ''
            ])
        
        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=registros.csv'}
        )
        
    except Exception as e:
        print(f"[ERROR] Erro ao exportar CSV: {str(e)}")
        flash('Erro ao exportar registros')
        return redirect(url_for('admin'))

@app.route('/export_all_tables')
@login_required
def export_all_tables():
    if not current_user.is_superuser:
        flash('Acesso negado')
        return redirect(url_for('admin'))
    
    try:
        # Criar diretório temporário
        import tempfile
        import zipfile
        import shutil
        
        temp_dir = tempfile.mkdtemp()
        
        try:
            # Exportar cada tabela
            tables = ['registros', 'anexos', 'users']
            for table in tables:
                data = query_db(f'SELECT * FROM {table}')
                
                with open(os.path.join(temp_dir, f'{table}.csv'), 'w', newline='') as f:
                    writer = csv.writer(f)
                    if data:
                        # Cabeçalho
                        writer.writerow(data[0].keys())
                        # Dados
                        for row in data:
                            writer.writerow(row.values())
            
            # Criar arquivo ZIP
            zip_path = os.path.join(temp_dir, 'backup.zip')
            with zipfile.ZipFile(zip_path, 'w') as zipf:
                for table in tables:
                    csv_path = os.path.join(temp_dir, f'{table}.csv')
                    zipf.write(csv_path, f'{table}.csv')
            
            # Enviar arquivo
            with open(zip_path, 'rb') as f:
                data = f.read()
                
            return Response(
                data,
                mimetype='application/zip',
                headers={'Content-Disposition': f'attachment; filename=backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.zip'}
            )
            
        finally:
            # Limpar diretório temporário
            shutil.rmtree(temp_dir)
            
    except Exception as e:
        print(f"[ERROR] Erro ao exportar tabelas: {str(e)}")
        flash('Erro ao exportar tabelas')
        return redirect(url_for('admin'))

@app.route('/import_csv', methods=['GET', 'POST'])
@login_required
def import_csv():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('Nenhum arquivo selecionado')
            return redirect(url_for('import_csv'))
        
        file = request.files['file']
        if file.filename == '':
            flash('Nenhum arquivo selecionado')
            return redirect(url_for('import_csv'))
        
        if not file.filename.endswith('.csv'):
            flash('Por favor, selecione um arquivo CSV')
            return redirect(url_for('import_csv'))
        
        try:
            # Ler o arquivo CSV
            stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
            csv_reader = csv.DictReader(stream)
            
            conn = get_db_connection()
            cur = conn.cursor()
            
            try:
                for row in csv_reader:
                    cur.execute("""
                        INSERT INTO registros (data, demanda, assunto, local, direcionamentos, status, ultimo_editor)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, [
                        row.get('Data', ''),
                        row.get('Demanda', ''),
                        row.get('Assunto', ''),
                        row.get('Local', ''),
                        row.get('Direcionamentos', ''),
                        row.get('Status', 'Pendente'),
                        current_user.username
                    ])
                
                conn.commit()
                flash('Registros importados com sucesso!')
                return redirect(url_for('report'))
                
            finally:
                cur.close()
                conn.close()
                
        except Exception as e:
            print(f"[ERROR] Erro ao importar CSV: {str(e)}")
            flash('Erro ao importar registros. Verifique o formato do arquivo.')
            return redirect(url_for('import_csv'))
    
    return render_template('import_csv.html')

@app.route('/update_settings', methods=['POST'])
@login_required
def update_settings():
    if not current_user.is_superuser:
        flash('Acesso negado')
        return redirect(url_for('admin'))
    
    try:
        per_page = request.form.get('per_page', type=int)
        session_timeout = request.form.get('session_timeout', type=int)
        auto_backup = request.form.get('auto_backup')
        
        # TODO: Implementar salvamento das configurações
        flash('Configurações atualizadas com sucesso')
        
    except Exception as e:
        print(f"[ERROR] Erro ao atualizar configurações: {str(e)}")
        flash('Erro ao atualizar configurações')
        
    return redirect(url_for('admin'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/form')
@login_required
def form():
    today = datetime.now().strftime('%Y-%m-%d')
    return render_template('form.html', today=today, form_data={})

@app.route('/report')
@login_required
def report():
    try:
        registros = query_db("""
            SELECT *, 
                   TO_CHAR(data, 'YYYY-MM-DD') as data_formatada,
                   TO_CHAR(data_ultima_edicao, 'YYYY-MM-DD HH24:MI:SS') as data_edicao_formatada
            FROM registros
            ORDER BY data DESC, id DESC
        """)
        for registro in registros:
            registro['data'] = registro['data_formatada']
            registro['data_ultima_edicao'] = registro['data_edicao_formatada']
        return render_template('report.html', registros=registros, status_list=STATUS_CHOICES)
    except Exception as e:
        print(f"[ERROR] Erro ao carregar relatório: {str(e)}")
        flash('Erro ao carregar o relatório. Por favor, tente novamente.')
        return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=False)
