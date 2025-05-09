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
    # Se o DATABASE_URL começa com postgres://, atualize para postgresql://
    if DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
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
    print("[INFO] Iniciando conexão com o banco de dados")
    print(f"[INFO] Ambiente de produção: {IS_PRODUCTION}")
    
        if IS_PRODUCTION:
            # Configuração para PostgreSQL no ambiente de produção (Render)
            print("[INFO] Conectando ao PostgreSQL...")
            conn = psycopg2.connect(DATABASE_URL)
            conn.cursor_factory = DictCursor
            print("[INFO] Conexão PostgreSQL estabelecida com sucesso")
            return conn
        else:
            # Configuração para SQLite no ambiente de desenvolvimento
            print("[INFO] Conectando ao SQLite...")
            conn = sqlite3.connect('database.db')
            conn.row_factory = sqlite3.Row
            print("[INFO] Conexão SQLite estabelecida com sucesso")
        print(f"[ERROR] Erro ao conectar ao banco de dados: {str(e)}")
        raise
# Função para consulta ao banco de dados
def query_db(query, args=(), one=False):
    print(f"[INFO] Executando query: {query}")
    print(f"[INFO] Argumentos: {args}")
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Adapta a query para PostgreSQL se estiver em produção
            query = query.replace('?', '%s')
        cur.execute(query, args)
        rv = cur.fetchall()
        print(f"[INFO] Query executada com sucesso. Resultados: {len(rv) if rv else 0}")
        cur.close()
        conn.close()
        return (rv[0] if rv else None) if one else rv
        print(f"[ERROR] Erro ao executar query: {str(e)}")
        print(f"Erro na consulta ao banco de dados: {str(e)}")
        if 'conn' in locals() and conn is not None:
            conn.close()
        raise e
# Função para garantir que a estrutura das tabelas existe
def ensure_tables():
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
                    INSERT INTO users (username, password, is_superuser)
                    VALUES ('admin', 'admin', TRUE)
                conn.commit()
                print("Tabela de usuários criada com sucesso! Usuário padrão: admin/admin")
            
            # Verifica se a tabela registros existe
            cur.execute("SELECT to_regclass('public.registros')")
                # Cria a tabela registros se não existir
                    CREATE TABLE registros (
                        data DATE,
                        demanda TEXT,
                        assunto TEXT,
                        status TEXT,
                        local TEXT,
                        direcionamentos TEXT,
                        ultimo_editor TEXT,
                        data_ultima_edicao TIMESTAMP WITH TIME ZONE,
                        anexos JSONB DEFAULT '[]'
                
            # Verifica se a tabela system_logs existe
            cur.execute("SELECT to_regclass('public.system_logs')")
                # Cria a tabela system_logs se não existir
                    CREATE TABLE system_logs (
                        timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        username TEXT,
                        action TEXT,
                        details TEXT,
                        ip_address TEXT
                # Registra o primeiro log de inicialização do sistema
                    INSERT INTO system_logs (username, action, details)
                    VALUES ('sistema', 'inicialização', 'Sistema iniciado com sucesso')
                print("Tabela de logs do sistema criada com sucesso!")
            # SQLite
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
            if not cur.fetchone():
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        is_superuser INTEGER DEFAULT 0
                    VALUES ('admin', 'admin', 1)
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='registros'")
                        data_ultima_edicao TIMESTAMP,
                        anexos TEXT DEFAULT '[]'
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='system_logs'")
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        print(f"Erro ao verificar tabelas: {str(e)}")
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
@app.route('/register', methods=['GET', 'POST'])
def register():
        confirm_password = request.form['confirm_password']
        if password != confirm_password:
            flash('As senhas não coincidem.')
            return redirect(url_for('register'))
        existing_user = query_db('SELECT * FROM users WHERE username = ?', [username], one=True)
        if existing_user:
            flash('Nome de usuário já existe.')
        query_db('INSERT INTO users (username, password, is_superuser) VALUES (?, ?, ?)',
                [username, password, False])
        flash('Usuário criado com sucesso!')
        return redirect(url_for('login'))
    return render_template('register.html')
@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
        username = request.form.get('username', '').strip()
        if not username:
            flash('Por favor, informe o nome de usuário.')
            return redirect(url_for('forgot_password'))
        user = query_db('SELECT * FROM users WHERE username = ?', [username], one=True)
            flash('Usuário não encontrado.')
        # Em um sistema real, aqui seria enviado um e-mail com link de redefinição
        # Como é uma versão simplificada, apenas resetamos para uma senha padrão
        query_db('UPDATE users SET password = ? WHERE id = ?', ['123456', user['id']])
        flash('Senha redefinida para: 123456. Por favor, altere sua senha após o login.')
    return render_template('forgot_password.html')
@app.route('/admin')
def admin():
    print("[INFO] Acessando rota /admin")
    print(f"[INFO] current_user: {current_user}, is_authenticated: {current_user.is_authenticated}")
        if not hasattr(current_user, 'is_superuser') or not current_user.is_superuser:
            print("[ERROR] Usuário não é superusuário")
            flash('Acesso negado: você não tem permissão para acessar essa página.')
            return redirect(url_for('form'))
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
            registros = query_db('SELECT * FROM registros ORDER BY data DESC')
        return render_template('admin.html', users=users, registros=registros)
        print(f"[ERROR] Erro na rota admin: {str(e)}")
        flash('Erro ao carregar página de administração.')
@app.route('/form', methods=['GET'])
def form():
    today = datetime.now().strftime('%Y-%m-%d')
    return render_template('form.html', 
                         status_list=STATUS_CHOICES,
                         form_data=request.form,
                         today=today)
@app.route('/submit', methods=['POST'])
def submit():
        data = request.form.get('data', '').strip()
        demanda = request.form.get('demanda', '').strip()
        assunto = request.form.get('assunto', '').strip()
        status = request.form.get('status', '').strip()
        if not all([data, demanda, assunto, status]):
            flash('Por favor, preencha todos os campos.')
        if status not in STATUS_CHOICES:
            flash('Por favor, selecione um status válido.')
        local = request.form.get('local', '').strip()
        direcionamentos = request.form.get('direcionamentos', '').strip()
        if not all([data, demanda, assunto, status, local]):
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
        flash(f'Erro ao salvar o registro: {str(e)}')
        print(f'Erro ao salvar o registro: {str(e)}')
@app.route('/estatisticas')
def estatisticas():
    # Obtém estatísticas para o dashboard
    stats = get_stats()
    # Busca os registros para a tabela de demandas recentes
    registros = query_db('''SELECT * FROM registros ORDER BY data DESC, id DESC''')
    return render_template('estatisticas.html', registros=registros, stats=stats)
@app.route('/report')
def report():
    print("[INFO] Acessando rota /report")
    if not current_user.is_authenticated:
        print("[ERROR] Usuário não autenticado")
        print("[INFO] Usuário autenticado, iniciando carregamento do relatório...")
        # Busca todos os registros ordenados por data (mais recentes primeiro)
        print("[DEBUG] Executando query para buscar registros...")
            registros = query_db('''
                SELECT *, 
                FROM registros
                ORDER BY data DESC, id DESC
            ''')
                SELECT * FROM registros
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
        print(f"[DEBUG] Erro ao carregar relatório: {str(e)}")
        print(f"[DEBUG] Traceback completo: {traceback.format_exc()}")
        flash('Erro ao carregar o relatório. Por favor, tente novamente.')
        return redirect(url_for('index'))
@app.route('/update_settings', methods=['POST'])
def update_settings():
    if not current_user.is_superuser:
        flash('Acesso negado: você não tem permissão para acessar essa página.')
    # Em uma versão real, aqui salvaria as configurações no banco de dados
    # Como é uma versão simplificada, apenas redirecionamos com uma mensagem
    flash('Configurações atualizadas com sucesso!')
    return redirect(url_for('admin'))
@app.route('/test_login')
def test_login():
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
def edit_registro(registro_id):
    # Busca o registro no banco de dados
    registro = query_db('SELECT * FROM registros WHERE id = ?', [registro_id], one=True)
    if not registro:
        flash('Registro não encontrado.')
        return redirect(url_for('report'))
    # Converte a string JSON de anexos para lista Python
    if 'anexos' in registro and registro['anexos']:
            if isinstance(registro['anexos'], str):
                registro['anexos'] = json.loads(registro['anexos'])
            # Se já for um objeto (no caso do PostgreSQL com JSONB), mantém como está
        except json.JSONDecodeError:
            registro['anexos'] = []
        registro['anexos'] = []
        # Obtém os dados do formulário
        # Valida os dados
            flash('Por favor, preencha todos os campos obrigatórios.')
            return render_template('edit.html', registro=registro, status_list=STATUS_CHOICES)
        # Atualiza o registro
        query_db('''
            UPDATE registros 
            SET data = ?, demanda = ?, assunto = ?, status = ?, local = ?, 
                direcionamentos = ?, ultimo_editor = ?, data_ultima_edicao = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', [data, demanda, assunto, status, local, direcionamentos, current_user.username, registro_id])
        flash('Registro atualizado com sucesso!')
    # Renderiza o template com os dados do registro
    return render_template('edit.html', registro=registro, status_list=STATUS_CHOICES)
# Rotas para gerenciamento de anexos
@app.route('/upload_anexo/<int:registro_id>', methods=['POST'])
def upload_anexo(registro_id):
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
            if 'anexos' in registro and registro['anexos']:
                if isinstance(registro['anexos'], str):
                    anexos = json.loads(registro['anexos'])
                    anexos = registro['anexos']
                anexos = []
        except (json.JSONDecodeError, TypeError):
            anexos = []
        # Gera um ID único para o anexo
        import uuid
        anexo_id = str(uuid.uuid4())
        filename = secure_filename(file.filename)
        # Processa o upload do arquivo
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
            # Em desenvolvimento, salva localmente
            unique_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            file.save(filepath)
                'nome_sistema': unique_filename,
                'tamanho': os.path.getsize(filepath)
        # Adiciona o novo anexo à lista
        anexos.append(novo_anexo)
        # Atualiza o registro no banco de dados
            # PostgreSQL (JSONB)
            query_db('UPDATE registros SET anexos = %s WHERE id = %s', [json.dumps(anexos), registro_id])
            # SQLite (TEXT)
            query_db('UPDATE registros SET anexos = ? WHERE id = ?', [json.dumps(anexos), registro_id])
        return jsonify({
            'success': True,
            'anexo': novo_anexo
        })
        print(f"Erro no upload de anexo: {str(e)}")
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500
