"""
Script de configuração do Notion
Cria o banco de dados de agendamentos automaticamente
"""

import os
from notion_client import Client
from dotenv import load_dotenv

load_dotenv()

def criar_database_agendamentos():
    """
    Cria o banco de dados de agendamentos no Notion
    """
    
    # Obter token e ID da página pai
    token = os.getenv("NOTION_TOKEN")
    parent_page_id = os.getenv("NOTION_PARENT_PAGE_ID")
    
    if not token:
        print("❌ NOTION_TOKEN não configurado no arquivo .env")
        return
    
    if not parent_page_id:
        print("❌ NOTION_PARENT_PAGE_ID não configurado no arquivo .env")
        print("   Crie uma página no Notion e copie o ID da URL")
        return
    
    # Inicializar cliente
    notion = Client(auth=token)
    
    print("🔄 Criando banco de dados no Notion...")
    
    try:
        # Criar banco de dados
        database = notion.databases.create(
            parent={"type": "page_id", "page_id": parent_page_id},
            title=[
                {
                    "type": "text",
                    "text": {
                        "content": "Agendamentos Wellington CR"
                    }
                }
            ],
            properties={
                "Nome": {
                    "title": {}
                },
                "Email": {
                    "email": {}
                },
                "Telefone": {
                    "phone_number": {}
                },
                "Data": {
                    "date": {}
                },
                "Horário": {
                    "rich_text": {}
                },
                "Tipo": {
                    "select": {
                        "options": [
                            {
                                "name": "Online",
                                "color": "blue"
                            },
                            {
                                "name": "Presencial",
                                "color": "green"
                            }
                        ]
                    }
                },
                "Status": {
                    "select": {
                        "options": [
                            {
                                "name": "Pendente",
                                "color": "yellow"
                            },
                            {
                                "name": "Confirmado",
                                "color": "green"
                            },
                            {
                                "name": "Cancelado",
                                "color": "red"
                            },
                            {
                                "name": "Realizado",
                                "color": "gray"
                            }
                        ]
                    }
                },
                "Mensagem": {
                    "rich_text": {}
                },
                "Criado em": {
                    "created_time": {}
                }
            }
        )
        
        database_id = database["id"]
        
        print(f"""
✅ Banco de dados criado com sucesso!

📋 COPIE E COLE NO SEU ARQUIVO .env:

NOTION_DATABASE_ID={database_id}

🔗 Link do banco de dados:
https://notion.so/{database_id.replace('-', '')}

⚠️  IMPORTANTE:
1. Adicione a linha acima no arquivo .env
2. Compartilhe o banco de dados com sua integração do Notion
3. Reinicie o servidor backend
        """)
        
        return database_id
        
    except Exception as e:
        print(f"❌ Erro ao criar banco de dados: {str(e)}")
        print("\nVerifique se:")
        print("  1. O NOTION_TOKEN está correto")
        print("  2. O NOTION_PARENT_PAGE_ID é válido")
        print("  3. A integração tem permissão para criar databases")
        return None

if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════╗
║  Configurador do Notion - Agenda Wellington CR          ║
╚══════════════════════════════════════════════════════════╝

Este script irá criar o banco de dados de agendamentos
no seu workspace do Notion.
    """)
    
    input("Pressione ENTER para continuar...")
    criar_database_agendamentos()
