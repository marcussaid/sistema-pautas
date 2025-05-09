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

if __name__ == '__main__':
    # Garantir que as tabelas do banco de dados existam
    ensure_tables()
    # Iniciar o servidor Flask
    app.run(debug=True, host='0.0.0.0', port=8000)
