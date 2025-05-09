import os
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from werkzeug.utils import secure_filename
from datetime import datetime

class S3Handler:
    def __init__(self):
        print("[INFO] Inicializando S3Handler...")
        
        # Verificar se estamos em produção
        self.is_production = os.environ.get('RENDER', 'false').lower() == 'true'
        
        if self.is_production:
            # Obter valores das variáveis de ambiente
            self.aws_access_key_id = os.environ.get('AWS_ACCESS_KEY_ID')
            self.aws_secret_access_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
            self.aws_region = os.environ.get('AWS_DEFAULT_REGION', 'us-east-1')
            self.bucket_name = os.environ.get('AWS_BUCKET_NAME')

            # Verificar se as credenciais necessárias estão presentes
            if not all([self.aws_access_key_id, self.aws_secret_access_key, self.bucket_name]):
                error_msg = "[ERROR] Credenciais AWS ausentes. Verifique as variáveis de ambiente."
                print(error_msg)
                raise Exception(error_msg)

            try:
                self.s3_client = boto3.client(
                    's3',
                    aws_access_key_id=self.aws_access_key_id,
                    aws_secret_access_key=self.aws_secret_access_key,
                    region_name=self.aws_region
                )

                # Verificar se podemos acessar o bucket
                self.s3_client.head_bucket(Bucket=self.bucket_name)
                print(f"[INFO] Conexão com bucket {self.bucket_name} estabelecida com sucesso")

            except Exception as e:
                error_msg = f"[ERROR] Erro ao inicializar S3 em produção: {str(e)}"
                print(error_msg)
                raise Exception(error_msg)
        else:
            print("[INFO] Ambiente de desenvolvimento detectado. S3 não será utilizado.")
            self.s3_client = None

    def upload_file(self, file, prefix='uploads/'):
        """
        Upload a file to S3 in production or save locally in development
        """
        if not file:
            error_msg = "[ERROR] Nenhum arquivo fornecido"
            print(error_msg)
            return {'success': False, 'error': error_msg}

        try:
            # Generate a secure filename with timestamp
            filename = secure_filename(file.filename)
            if not filename:
                error_msg = "[ERROR] Nome de arquivo inválido"
                print(error_msg)
                return {'success': False, 'error': error_msg}

            unique_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"

            if self.is_production:
                print(f"[INFO] Iniciando upload do arquivo {filename} para S3...")
                s3_path = f"{prefix}{unique_filename}"

                # Reset file pointer to beginning
                file.seek(0)

                # Upload the file to S3
                self.s3_client.upload_fileobj(file, self.bucket_name, s3_path)

                # Generate the URL
                url = f"https://{self.bucket_name}.s3.amazonaws.com/{s3_path}"
                print(f"[INFO] Upload concluído. URL gerada: {url}")

                return {
                    'success': True,
                    'filename': unique_filename,
                    'original_name': filename,
                    's3_path': s3_path,
                    'url': url
                }
            else:
                # Em desenvolvimento, salva localmente
                upload_folder = os.environ.get('UPLOAD_FOLDER', 'uploads')
                if not os.path.exists(upload_folder):
                    os.makedirs(upload_folder)
                
                filepath = os.path.join(upload_folder, unique_filename)
                file.save(filepath)
                print(f"[INFO] Arquivo salvo localmente em: {filepath}")

                return {
                    'success': True,
                    'filename': unique_filename,
                    'original_name': filename,
                    'filepath': filepath
                }

        except Exception as e:
            error_msg = f"[ERROR] Erro ao processar arquivo: {str(e)}"
            print(error_msg)
            return {
                'success': False,
                'error': error_msg
            }

    def download_file(self, s3_path):
        """
        Download a file from S3 in production or read locally in development
        """
        if not self.is_production:
            print("[INFO] Ambiente de desenvolvimento, operação não suportada")
            return None

        try:
            print(f"[INFO] Baixando arquivo {s3_path} do S3...")
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=s3_path)
            return response['Body'].read()
        except Exception as e:
            print(f"[ERROR] Erro ao baixar arquivo: {str(e)}")
            return None

    def delete_file(self, s3_path):
        """
        Delete a file from S3 in production or locally in development
        """
        if not self.is_production:
            print("[INFO] Ambiente de desenvolvimento, operação não suportada")
            return False

        try:
            print(f"[INFO] Deletando arquivo {s3_path} do S3...")
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_path)
            return True
        except Exception as e:
            print(f"[ERROR] Erro ao deletar arquivo: {str(e)}")
            return False

    def get_file_url(self, s3_path):
        """
        Get the URL for a file in S3 (production only)
        """
        if not self.is_production:
            print("[INFO] Ambiente de desenvolvimento, operação não suportada")
            return None

        try:
            print(f"[INFO] Gerando URL para {s3_path}...")
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': s3_path
                },
                ExpiresIn=3600  # URL expires in 1 hour
            )
            return url
        except Exception as e:
            print(f"[ERROR] Erro ao gerar URL: {str(e)}")
            return None
