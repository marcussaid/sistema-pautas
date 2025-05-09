# Sistema de Registro de Demandas

Sistema web para registro e acompanhamento de demandas desenvolvido com Flask.

## Funcionalidades

- Registro de demandas com data, descrição, assunto e status
- Visualização de demandas em formato de relatório
- Banco de dados persistente
- Interface responsiva com Tailwind CSS

## Requisitos

- Python 3.8+
- Flask
- PostgreSQL (produção) ou SQLite (desenvolvimento)

## Configuração Local

1. Clone o repositório:
```bash
git clone https://github.com/marcussaid/sistema-pautas.git
cd sistema-pautas
```

2. Crie um ambiente virtual e ative-o:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

3. Crie um arquivo `.env` baseado no template:
```bash
cp env.template .env
```

4. Configure as variáveis de ambiente no arquivo `.env`:
   - Para desenvolvimento local, apenas `UPLOAD_FOLDER` é obrigatório
   - Para produção, configure todas as variáveis AWS S3

5. Instale as dependências:
```bash
pip install -r requirements.txt
```

6. Execute a aplicação:
```bash
python app.py
```

A aplicação estará disponível em `http://localhost:8000`

### Upload de Arquivos
- Em desenvolvimento: os arquivos são salvos na pasta local definida em `UPLOAD_FOLDER`
- Em produção: os arquivos são armazenados no AWS S3

## Implantação no Render.com

1. Crie uma conta no [Render.com](https://render.com)

2. Crie um novo Web Service:
   - Conecte ao repositório https://github.com/marcussaid/sistema-pautas.git
   - Selecione a branch principal
   - Selecione "Python" como ambiente
   - Configure o comando de build: `pip install -r requirements.txt`
   - Configure o comando de start: `gunicorn app:app`

3. Configure as variáveis de ambiente:
   - `DATABASE_URL`: URL de conexão do PostgreSQL
   - `SECRET_KEY`: Chave secreta para a aplicação Flask
   - `AWS_ACCESS_KEY_ID`: Chave de acesso AWS para upload de arquivos
   - `AWS_SECRET_ACCESS_KEY`: Chave secreta AWS
   - `AWS_DEFAULT_REGION`: Região AWS (ex: us-east-1)
   - `AWS_BUCKET_NAME`: Nome do bucket S3
   - `RENDER`: true

4. Clique em "Create Web Service"

## Variáveis de Ambiente

### AWS S3 (Produção)
- `AWS_ACCESS_KEY_ID`: Chave de acesso AWS
- `AWS_SECRET_ACCESS_KEY`: Chave secreta AWS
- `AWS_DEFAULT_REGION`: Região AWS (padrão: us-east-1)
- `AWS_BUCKET_NAME`: Nome do bucket S3 para armazenamento de anexos

### Aplicação
- `DATABASE_URL`: URL de conexão do banco de dados (PostgreSQL em produção, SQLite em desenvolvimento)
- `SECRET_KEY`: Chave secreta para a aplicação Flask
- `PORT`: Porta para executar a aplicação (opcional, padrão: 8000)
- `RENDER`: Flag para indicar ambiente de produção
- `UPLOAD_FOLDER`: Pasta para uploads locais em desenvolvimento

## Estrutura do Projeto

```
.
├── app.py              # Aplicação principal
├── s3_utils.py         # Utilitários para AWS S3
├── requirements.txt    # Dependências do projeto
├── Procfile           # Configuração para o Render.com
├── render.yaml        # Configuração do Render
├── env.template       # Template de variáveis de ambiente
├── .gitignore         # Arquivos ignorados pelo Git
├── uploads/           # Pasta para uploads locais
└── templates/         # Templates HTML
    ├── base.html      # Template base
    ├── form.html      # Formulário de registro
    ├── edit.html      # Edição de registros
    └── report.html    # Relatório de demandas
```

## Desenvolvimento

Para desenvolvimento local, a aplicação usa SQLite por padrão. Para usar PostgreSQL localmente, configure a variável de ambiente `DATABASE_URL` com a URL de conexão do PostgreSQL.

## Segurança

### Credenciais AWS
- Nunca commite o arquivo `.env` ou exponha credenciais AWS no código
- Use um usuário IAM com permissões mínimas necessárias para o S3
- Configure as políticas de bucket S3 adequadamente
- Em produção, use variáveis de ambiente seguras do Render.com
- Rotacione as chaves AWS periodicamente

### Uploads
- Em desenvolvimento: os arquivos são salvos localmente
- Em produção: os arquivos são armazenados de forma segura no S3
- Validação de tipos de arquivo permitidos
- Limite de tamanho de upload configurável

## Contribuindo

1. Faça um Fork do projeto
2. Crie uma branch para sua feature (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

## Licença

MIT
