import os
import boto3
from botocore.exceptions import ClientError
from werkzeug.utils import secure_filename
from datetime import datetime

class S3Handler:
    def __init__(self):
        print("[INFO] Inicializando S3Handler para produção...")
        
        # Obter credenciais do S3
        self.aws_access_key_id = os.environ.get('AWS_ACCESS_KEY_ID')
        self.aws_secret_access_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
        self.aws_region = os.environ.get('AWS_DEFAULT_REGION', 'us-east-1')
        self.bucket_name = os.environ.get('AWS_BUCKET_NAME')

        if not all([self.aws_access_key_id, self.aws_secret_access_key, self.bucket_name]):
            error_msg = "[ERROR] Credenciais AWS ausentes. Verifique as variáveis de ambiente."
            print(error_msg)
            raise Exception(error_msg)

        try:
            # Inicializar cliente S3
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key,
                region_name=self.aws_region
            )

            # Verificar acesso ao bucket
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            print(f"[INFO] Conexão com bucket {self.bucket_name} estabelecida com sucesso")

        except Exception as e:
            error_msg = f"[ERROR] Erro ao inicializar S3: {str(e)}"
            print(error_msg)
            raise Exception(error_msg)

    def upload_fileobj(self, file, s3_key):
        """Upload um objeto de arquivo para o S3"""
        try:
            print(f"[INFO] Fazendo upload do arquivo para {s3_key}")
            self.s3_client.upload_fileobj(file, self.bucket_name, s3_key)
            return True
        except Exception as e:
            print(f"[ERROR] Erro no upload do arquivo: {str(e)}")
            return False

    def delete_file(self, s3_key):
        """Excluir um arquivo do S3"""
        try:
            print(f"[INFO] Excluindo arquivo {s3_key}")
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)
            return True
        except Exception as e:
            print(f"[ERROR] Erro ao excluir arquivo: {str(e)}")
            return False

    def get_file_url(self, s3_key, expires_in=3600):
        """Gerar URL pré-assinada para um arquivo"""
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': s3_key
                },
                ExpiresIn=expires_in
            )
            return url
        except Exception as e:
            print(f"[ERROR] Erro ao gerar URL: {str(e)}")
            return None

    def get_file(self, s3_key):
        """Baixar um arquivo do S3"""
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=s3_key)
            return response['Body'].read()
        except Exception as e:
            print(f"[ERROR] Erro ao baixar arquivo: {str(e)}")
            return None

    def process_upload(self, file, prefix='uploads/'):
        """Processar upload de arquivo com nome seguro e timestamp"""
        if not file:
            return {'success': False, 'error': 'Nenhum arquivo fornecido'}

        try:
            filename = secure_filename(file.filename)
            if not filename:
                return {'success': False, 'error': 'Nome de arquivo inválido'}

            # Gerar nome único com timestamp
            unique_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
            s3_key = f"{prefix}{unique_filename}"

            # Reset do ponteiro do arquivo
            file.seek(0)

            # Upload para S3
            if self.upload_fileobj(file, s3_key):
                url = f"https://{self.bucket_name}.s3.amazonaws.com/{s3_key}"
                return {
                    'success': True,
                    'filename': unique_filename,
                    'original_name': filename,
                    's3_key': s3_key,
                    'url': url
                }
            else:
                return {'success': False, 'error': 'Erro no upload para S3'}

        except Exception as e:
            error_msg = f"Erro ao processar arquivo: {str(e)}"
            print(f"[ERROR] {error_msg}")
            return {'success': False, 'error': error_msg}
