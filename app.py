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

@login_manager.unauthorized_handler
def unauthorized():
    print("[ERROR] Acesso não autorizado detectado")
    print(f"[INFO] URL atual: {request.url}")
    print(f"[INFO] Método: {request.method}")
    flash('Por favor, faça login para acessar esta página.')
    return redirect(url_for('login'))

print("[INFO] Login Manager configurado com sucesso")

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

# Função para garantir que a estrutura das tabelas existe
def ensure_tables():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        if IS_PRODUCTION:
            # PostgreSQL
            # Verifica se a tabela users existe
            cur.execute("SELECT to_regclass('public.users')")
            if not cur.fetchone()[0]:
                # Cria a tabela users se não existir
                cur.execute('''
                    CREATE TABLE users (
                        id SERIAL PRIMARY KEY,
                        username TEXT UNIQUE NOT NULL,
                        password TEXT NOT NULL,
                        is_superuser BOOLEAN DEFAULT FALSE
                    )
                ''')
                # Cria um superusuário padrão
                cur.execute('''
                    INSERT INTO users (username, password, is_superuser)
                    VALUES ('admin', 'admin', TRUE)
                ''')
                conn.commit()
                print("Tabela de usuários criada com sucesso! Usuário padrão: admin/admin")
            
            # Verifica se a tabela registros existe
            cur.execute("SELECT to_regclass('public.registros')")
            if not cur.fetchone()[0]:
                # Cria a tabela registros se não existir
                cur.execute('''
                    CREATE TABLE registros (
                        id SERIAL PRIMARY KEY,
                        data DATE,
                        demanda TEXT,
                        assunto TEXT,
                        status TEXT,
                        local TEXT,
                        direcionamentos TEXT,
                        ultimo_editor TEXT,
                        data_ultima_edicao TIMESTAMP WITH TIME ZONE,
                        anexos JSONB DEFAULT '[]'
                    )
                ''')
                conn.commit()
                
            # Verifica se a tabela system_logs existe
            cur.execute("SELECT to_regclass('public.system_logs')")
            if not cur.fetchone()[0]:
                # Cria a tabela system_logs se não existir
                cur.execute('''
                    CREATE TABLE system_logs (
                        id SERIAL PRIMARY KEY,
                        timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        username TEXT,
                        action TEXT,
                        details TEXT,
                        ip_address TEXT
                    )
                ''')
                # Registra o primeiro log de inicialização do sistema
                cur.execute('''
                    INSERT INTO system_logs (username, action, details)
                    VALUES ('sistema', 'inicialização', 'Sistema iniciado com sucesso')
                ''')
                conn.commit()
                print("Tabela de logs do sistema criada com sucesso!")
        else:
            # SQLite
            # Verifica se a tabela users existe
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
            if not cur.fetchone():
                # Cria a tabela users se não existir
                cur.execute('''
                    CREATE TABLE users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE NOT NULL,
                        password TEXT NOT NULL,
                        is_superuser INTEGER DEFAULT 0
                    )
                ''')
                # Cria um superusuário padrão
                cur.execute('''
                    INSERT INTO users (username, password, is_superuser)
                    VALUES ('admin', 'admin', 1)
                ''')
                conn.commit()
                print("Tabela de usuários criada com sucesso! Usuário padrão: admin/admin")
            
            # Verifica se a tabela registros existe
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='registros'")
            if not cur.fetchone():
                # Cria a tabela registros se não existir
                cur.execute('''
                    CREATE TABLE registros (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        data DATE,
                        demanda TEXT,
                        assunto TEXT,
                        status TEXT,
                        local TEXT,
                        direcionamentos TEXT,
                        ultimo_editor TEXT,
                        data_ultima_edicao TIMESTAMP,
                        anexos TEXT DEFAULT '[]'
                    )
                ''')
                conn.commit()
                
            # Verifica se a tabela system_logs existe
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='system_logs'")
            if not cur.fetchone():
                # Cria a tabela system_logs se não existir
                cur.execute('''
                    CREATE TABLE system_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        username TEXT,
                        action TEXT,
                        details TEXT,
                        ip_address TEXT
                    )
                ''')
                # Registra o primeiro log de inicialização do sistema
                cur.execute('''
                    INSERT INTO system_logs (username, action, details)
                    VALUES ('sistema', 'inicialização', 'Sistema iniciado com sucesso')
                ''')
                conn.commit()
                print("Tabela de logs do sistema criada com sucesso!")
        
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Erro ao verificar tabelas: {str(e)}")
        if 'conn' in locals() and conn is not None:
            conn.close()

# Inicialização do banco de dados
ensure_tables()

# Função para obter estatísticas dos registros
def get_stats():
    # Conta o total de registros
    total_registros = query_db('SELECT COUNT(*) as count FROM registros', one=True)['count']
    
    # Obtém a data de hoje
    hoje = date.today().strftime('%Y-%m-%d')
    
    # Conta registros de hoje
    registros_hoje = query_db('SELECT COUNT(*) as count FROM registros WHERE data = ?', [hoje], one=True)['count']
    
    # Conta registros pendentes
    registros_pendentes = query_db('SELECT COUNT(*) as count FROM registros WHERE status = ?', ['Pendente'], one=True)['count']
    
    # Conta registros por status
    status_counts = {}
    for status in STATUS_CHOICES:
        count = query_db('SELECT COUNT(*) as count FROM registros WHERE status = ?', [status], one=True)['count']
        status_counts[status] = count
    
    # Retorna as estatísticas
    return {
        'total_registros': total_registros,
        'registros_hoje': registros_hoje,
        'registros_pendentes': registros_pendentes,
        'status_counts': status_counts
    }

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

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        if password != confirm_password:
            flash('As senhas não coincidem.')
            return redirect(url_for('register'))
            
        existing_user = query_db('SELECT * FROM users WHERE username = ?', [username], one=True)
        if existing_user:
            flash('Nome de usuário já existe.')
            return redirect(url_for('register'))
            
        query_db('INSERT INTO users (username, password, is_superuser) VALUES (?, ?, ?)',
                [username, password, False])
        flash('Usuário criado com sucesso!')
        return redirect(url_for('login'))
        
    return render_template('register.html')

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        
        if not username:
            flash('Por favor, informe o nome de usuário.')
            return redirect(url_for('forgot_password'))
            
        user = query_db('SELECT * FROM users WHERE username = ?', [username], one=True)
        if not user:
            flash('Usuário não encontrado.')
            return redirect(url_for('forgot_password'))
            
        # Em um sistema real, aqui seria enviado um e-mail com link de redefinição
        # Como é uma versão simplificada, apenas resetamos para uma senha padrão
        query_db('UPDATE users SET password = ? WHERE id = ?', ['123456', user['id']])
        flash('Senha redefinida para: 123456. Por favor, altere sua senha após o login.')
        return redirect(url_for('login'))
        
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
            
        users = query_db('SELECT * FROM users ORDER BY username')
        
        # Obtém estatísticas atualizadas do banco de dados
        stats = get_stats()
        stats['total_usuarios'] = len(users)
        
        # Busca os logs mais recentes do sistema - versão compatível
        try:
            # Seleciona todas as colunas disponíveis para maior compatibilidade
            system_logs = query_db('''
                SELECT id, timestamp, username, action, details, ip_address, message, level, created_at
                FROM system_logs 
                ORDER BY timestamp DESC, created_at DESC
                LIMIT 50
            ''')
        except Exception as e:
            system_logs = []
            flash(f"Erro ao buscar logs do sistema: {str(e)}")
            print(f"Erro ao buscar logs do sistema: {str(e)}")
        
        # Formata os logs para exibição
        formatted_logs = []
        for log in system_logs:
            try:
                # Usa timestamp se disponível, senão usa created_at
                timestamp = log.get('timestamp', log.get('created_at', 'N/A'))
                
                # Formata a data/hora para exibição
                if isinstance(timestamp, str):
                    # Analisa a string de data/hora
                    try:
                        from datetime import datetime
                        timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    except:
                        # Mantém como string se não conseguir converter
                        pass
                
                # Usa username se disponível
                username = log.get('username', 'sistema')
                
                # Usa action e details primariamente, message como fallback
                if log.get('action') and log.get('details'):
                    action = log.get('action', '')
                    details = log.get('details', '')
                    formatted_log = f"[{timestamp}] {username}: {action} - {details}"
                else:
                    # Use message quando action/details não estão disponíveis
                    message = log.get('message', 'Sem detalhes')
                    level = log.get('level', 'info')
                    formatted_log = f"[{timestamp}] {username} [{level}]: {message}"
                
                formatted_logs.append(formatted_log)
            except Exception as log_error:
                formatted_logs.append(f"[Erro ao formatar log] {str(log_error)}")
        
        settings = {
            'per_page': 10,
            'session_timeout': 60,
            'auto_backup': 'daily'
        }
        
        return render_template('admin.html', users=users, stats=stats, system_logs=formatted_logs, settings=settings)
    except Exception as e:
        import traceback
        error_message = f"Erro interno na página de administração: {str(e)}"
        print(error_message)
        print(traceback.format_exc())
        flash(error_message)
        return redirect(url_for('index'))

@app.route('/admin/user/<int:user_id>', methods=['PUT'])
@login_required
def update_user(user_id):
    if not current_user.is_superuser:
        return jsonify({'success': False, 'message': 'Acesso negado'}), 403
        
    data = request.get_json()
    username = data.get('username')
    is_superuser = data.get('is_superuser')
    password = data.get('password')
    
    if not username:
        return jsonify({'success': False, 'message': 'Nome de usuário não pode estar vazio'}), 400
        
    try:
        if password:
            # Se uma nova senha foi fornecida, atualize-a também
            query_db('UPDATE users SET username = ?, is_superuser = ?, password = ? WHERE id = ?', 
                    [username, is_superuser, password, user_id])
        else:
            # Caso contrário, apenas atualize o nome de usuário e o status de superusuário
            query_db('UPDATE users SET username = ?, is_superuser = ? WHERE id = ?', 
                    [username, is_superuser, user_id])
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/admin/user/<int:user_id>', methods=['DELETE', 'POST'])
@login_required
def delete_user(user_id):
    if not current_user.is_superuser:
        flash('Acesso negado: você não tem permissão para realizar essa ação.')
        return redirect(url_for('admin'))
        
    if current_user.id == user_id:
        flash('Você não pode excluir sua própria conta!')
        return redirect(url_for('admin'))
        
    query_db('DELETE FROM users WHERE id = ?', [user_id])
    flash('Usuário excluído com sucesso!')
    return redirect(url_for('admin'))

@app.route('/form', methods=['GET'])
@login_required
def form():
    today = datetime.now().strftime('%Y-%m-%d')
    return render_template('form.html', 
                         status_list=STATUS_CHOICES,
                         form_data=request.form,
                         today=today)

@app.route('/submit', methods=['POST'])
@login_required
def submit():
    try:
        data = request.form.get('data', '').strip()
        demanda = request.form.get('demanda', '').strip()
        assunto = request.form.get('assunto', '').strip()
        status = request.form.get('status', '').strip()

        if not all([data, demanda, assunto, status]):
            flash('Por favor, preencha todos os campos.')
            return redirect(url_for('form'))

        if status not in STATUS_CHOICES:
            flash('Por favor, selecione um status válido.')
            return redirect(url_for('form'))

        local = request.form.get('local', '').strip()
        direcionamentos = request.form.get('direcionamentos', '').strip()
        
        if not all([data, demanda, assunto, status, local]):
            flash('Por favor, preencha todos os campos.')
            return redirect(url_for('form'))

        # Garante que a coluna anexos existe
        ensure_tables()

        # Insere o registro
        query = '''
            INSERT INTO registros 
            (data, demanda, assunto, status, local, direcionamentos, ultimo_editor, data_ultima_edicao) 
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        '''
        query_db(query, [
            data, demanda, assunto, status, local, direcionamentos, 
            current_user.username
        ])
        
        flash('Registro salvo com sucesso!')
        return redirect(url_for('form'))

    except Exception as e:
        flash(f'Erro ao salvar o registro: {str(e)}')
        print(f'Erro ao salvar o registro: {str(e)}')
        return redirect(url_for('form'))

@app.route('/estatisticas')
@login_required
def estatisticas():
    # Obtém estatísticas para o dashboard
    stats = get_stats()
    
    # Busca os registros para a tabela de demandas recentes
    registros = query_db('''SELECT * FROM registros ORDER BY data DESC, id DESC''')
    
    return render_template('estatisticas.html', registros=registros, stats=stats)

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
        registros = query_db('''
            SELECT * FROM registros
            ORDER BY data DESC, id DESC
        ''')
        print(f"[DEBUG] {len(registros) if registros else 0} registros encontrados")
        
        # Processa os anexos de cada registro
        print("[DEBUG] Processando anexos dos registros...")
        for registro in registros:
            try:
                if 'anexos' in registro and registro['anexos']:
                    print(f"[DEBUG] Processando anexos do registro {registro.get('id')}")
                    print(f"[DEBUG] Tipo dos anexos: {type(registro['anexos'])}")
                    print(f"[DEBUG] Conteúdo dos anexos: {registro['anexos']}")
                    
                    # Se for string (SQLite), converte para JSON
                    if isinstance(registro['anexos'], str):
                        try:
                            registro['anexos'] = json.loads(registro['anexos'])
                            print(f"[DEBUG] Anexos convertidos com sucesso para JSON")
                        except json.JSONDecodeError as je:
                            print(f"[DEBUG] Erro ao decodificar JSON dos anexos: {str(je)}")
                            registro['anexos'] = []
                    # Se já for um objeto (PostgreSQL JSONB), mantém como está
                    elif not isinstance(registro['anexos'], list):
                        print(f"[DEBUG] Anexos não são uma lista, resetando para lista vazia")
                        registro['anexos'] = []
                else:
                    print(f"[DEBUG] Registro {registro.get('id')} não tem anexos")
                    registro['anexos'] = []
            except Exception as e:
                print(f"[DEBUG] Erro ao processar anexos do registro {registro.get('id')}: {str(e)}")
                print(f"[DEBUG] Traceback completo: {traceback.format_exc()}")
                registro['anexos'] = []
        
        print("[DEBUG] Renderizando template...")
        return render_template('report.html', registros=registros, status_list=STATUS_CHOICES)
    except Exception as e:
        print(f"[DEBUG] Erro ao carregar relatório: {str(e)}")
        print(f"[DEBUG] Traceback completo: {traceback.format_exc()}")
        flash('Erro ao carregar o relatório. Por favor, tente novamente.')
        return redirect(url_for('index'))

@app.route('/update_settings', methods=['POST'])
@login_required
def update_settings():
    if not current_user.is_superuser:
        flash('Acesso negado: você não tem permissão para acessar essa página.')
        return redirect(url_for('form'))
        
    # Em uma versão real, aqui salvaria as configurações no banco de dados
    # Como é uma versão simplificada, apenas redirecionamos com uma mensagem
    flash('Configurações atualizadas com sucesso!')
    return redirect(url_for('admin'))

@app.route('/test_login')
def test_login():
    if current_user.is_authenticated:
        is_admin = current_user.is_superuser
        result = {
            'authenticated': True,
            'username': current_user.username,
            'is_superuser': is_admin,
            'id': current_user.id
        }
    else:
        result = {'authenticated': False}
    
    return jsonify(result)

# Rotas para edição de registros
@app.route('/edit/<int:registro_id>', methods=['GET', 'POST'])
@login_required
def edit_registro(registro_id):
    # Busca o registro no banco de dados
    registro = query_db('SELECT * FROM registros WHERE id = ?', [registro_id], one=True)
    
    if not registro:
        flash('Registro não encontrado.')
        return redirect(url_for('report'))
    
    # Converte a string JSON de anexos para lista Python
    if 'anexos' in registro and registro['anexos']:
        try:
            if isinstance(registro['anexos'], str):
                registro['anexos'] = json.loads(registro['anexos'])
            # Se já for um objeto (no caso do PostgreSQL com JSONB), mantém como está
        except json.JSONDecodeError:
            registro['anexos'] = []
    else:
        registro['anexos'] = []
    
    if request.method == 'POST':
        # Obtém os dados do formulário
        data = request.form.get('data', '').strip()
        demanda = request.form.get('demanda', '').strip()
        assunto = request.form.get('assunto', '').strip()
        status = request.form.get('status', '').strip()
        local = request.form.get('local', '').strip()
        direcionamentos = request.form.get('direcionamentos', '').strip()
        
        # Valida os dados
        if not all([data, demanda, assunto, status, local]):
            flash('Por favor, preencha todos os campos obrigatórios.')
            return render_template('edit.html', registro=registro, status_list=STATUS_CHOICES)
        
        if status not in STATUS_CHOICES:
            flash('Por favor, selecione um status válido.')
            return render_template('edit.html', registro=registro, status_list=STATUS_CHOICES)
        
        # Atualiza o registro
        query_db('''
            UPDATE registros 
            SET data = ?, demanda = ?, assunto = ?, status = ?, local = ?, 
                direcionamentos = ?, ultimo_editor = ?, data_ultima_edicao = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', [data, demanda, assunto, status, local, direcionamentos, current_user.username, registro_id])
        
        flash('Registro atualizado com sucesso!')
        return redirect(url_for('report'))
    
    # Renderiza o template com os dados do registro
    return render_template('edit.html', registro=registro, status_list=STATUS_CHOICES)

# Rotas para gerenciamento de anexos
@app.route('/upload_anexo/<int:registro_id>', methods=['POST'])
@login_required
def upload_anexo(registro_id):
    try:
        # Verifica se o registro existe
        registro = query_db('SELECT * FROM registros WHERE id = ?', [registro_id], one=True)
        if not registro:
            return jsonify({'error': 'Registro não encontrado.'}), 404
        
        # Verifica se um arquivo foi enviado
        if 'file' not in request.files:
            return jsonify({'error': 'Nenhum arquivo enviado.'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'Nenhum arquivo selecionado.'}), 400
        
        # Obtém os anexos atuais
        try:
            if 'anexos' in registro and registro['anexos']:
                if isinstance(registro['anexos'], str):
                    anexos = json.loads(registro['anexos'])
                else:
                    anexos = registro['anexos']
            else:
                anexos = []
        except (json.JSONDecodeError, TypeError):
            anexos = []

        # Gera um ID único para o anexo
        import uuid
        anexo_id = str(uuid.uuid4())
        filename = secure_filename(file.filename)

        # Processa o upload do arquivo
        if IS_PRODUCTION:
            # Em produção, usa S3
            result = s3.upload_file(file)
            if not result['success']:
                return jsonify({'error': 'Erro ao fazer upload do arquivo.'}), 500
            
            novo_anexo = {
                'id': anexo_id,
                'nome_original': filename,
                'nome_sistema': result['filename'],
                'data_upload': datetime.now().isoformat(),
                'tamanho': file.content_length or 0,
                's3_path': result['s3_path'],
                'url': result['url']
            }
        else:
            # Em desenvolvimento, salva localmente
            unique_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            file.save(filepath)
            
            novo_anexo = {
                'id': anexo_id,
                'nome_original': filename,
                'nome_sistema': unique_filename,
                'data_upload': datetime.now().isoformat(),
                'tamanho': os.path.getsize(filepath)
            }

        # Adiciona o novo anexo à lista
        anexos.append(novo_anexo)
        
        # Atualiza o registro no banco de dados
        if IS_PRODUCTION:
            # PostgreSQL (JSONB)
            query_db('UPDATE registros SET anexos = %s WHERE id = %s', [json.dumps(anexos), registro_id])
        else:
            # SQLite (TEXT)
            query_db('UPDATE registros SET anexos = ? WHERE id = ?', [json.dumps(anexos), registro_id])
        
        return jsonify({
            'success': True,
            'anexo': novo_anexo
        })
    except Exception as e:
        print(f"Erro no upload de anexo: {str(e)}")
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500
