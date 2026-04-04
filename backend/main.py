from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, validator
from datetime import datetime, timedelta
from typing import List, Optional
import os
from notion_client import Client
import logging
from dotenv import load_dotenv

load_dotenv()

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Inicializar FastAPI
app = FastAPI(
    title="Agenda Wellington CR",
    description="Sistema de agendamento integrado ao Notion",
    version="1.0.0"
)

# CORS - Permitir requisições do site
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Em produção, especifique o domínio do site
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuração do Notion
NOTION_TOKEN = os.getenv("NOTION_TOKEN", "")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID", "")

# Inicializar cliente Notion
notion = Client(auth=NOTION_TOKEN) if NOTION_TOKEN else None

# Horários disponíveis (Segunda a Sexta, 14h às 22h)
HORARIOS_DISPONIVEIS = {
    "monday": ["14:00", "15:00", "16:00", "17:00", "18:00", "19:00", "20:00", "21:00"],
    "tuesday": ["14:00", "15:00", "16:00", "17:00", "18:00", "19:00", "20:00", "21:00"],
    "wednesday": ["14:00", "15:00", "16:00", "17:00", "18:00", "19:00", "20:00", "21:00"],
    "thursday": ["14:00", "15:00", "16:00", "17:00", "18:00", "19:00", "20:00", "21:00"],
    "friday": ["14:00", "15:00", "16:00", "17:00", "18:00", "19:00", "20:00", "21:00"],
}

# Modelos Pydantic
class AgendamentoCreate(BaseModel):
    nome: str
    email: EmailStr
    telefone: str
    data: str  # YYYY-MM-DD
    horario: str  # HH:MM
    tipo_atendimento: str  # "online" ou "presencial"
    mensagem: Optional[str] = ""
    
    @validator('nome')
    def nome_valido(cls, v):
        if len(v) < 3:
            raise ValueError('Nome deve ter pelo menos 3 caracteres')
        return v.strip()
    
    @validator('telefone')
    def telefone_valido(cls, v):
        # Remove caracteres não numéricos
        numeros = ''.join(filter(str.isdigit, v))
        if len(numeros) < 10:
            raise ValueError('Telefone inválido')
        return v.strip()
    
    @validator('data')
    def data_valida(cls, v):
        try:
            data = datetime.strptime(v, '%Y-%m-%d')
            if data.date() < datetime.now().date():
                raise ValueError('Data não pode ser no passado')
            return v
        except ValueError as e:
            raise ValueError(f'Data inválida: {str(e)}')
    
    @validator('horario')
    def horario_valido(cls, v):
        if not v or ':' not in v:
            raise ValueError('Horário inválido')
        return v.strip()
    
    @validator('tipo_atendimento')
    def tipo_valido(cls, v):
        if v.lower() not in ['online', 'presencial']:
            raise ValueError('Tipo deve ser "online" ou "presencial"')
        return v.lower()

class SlotDisponivel(BaseModel):
    data: str
    horario: str
    disponivel: bool

class DisponibilidadeResponse(BaseModel):
    data: str
    slots: List[SlotDisponivel]

# Funções auxiliares
def criar_database_notion():
    """
    Cria o banco de dados no Notion para agendamentos
    Execute esta função uma vez para configurar
    """
    if not notion:
        raise Exception("Notion token não configurado")
    
    # Propriedades do banco de dados
    properties = {
        "Nome": {"title": {}},
        "Email": {"email": {}},
        "Telefone": {"phone_number": {}},
        "Data": {"date": {}},
        "Horário": {"rich_text": {}},
        "Tipo": {
            "select": {
                "options": [
                    {"name": "Online", "color": "blue"},
                    {"name": "Presencial", "color": "green"}
                ]
            }
        },
        "Status": {
            "select": {
                "options": [
                    {"name": "Pendente", "color": "yellow"},
                    {"name": "Confirmado", "color": "green"},
                    {"name": "Cancelado", "color": "red"},
                    {"name": "Realizado", "color": "gray"}
                ]
            }
        },
        "Mensagem": {"rich_text": {}},
        "Criado em": {"created_time": {}}
    }
    
    # Criar database (precisa ser executado manualmente com parent_page_id)
    logger.info("Database schema pronto para criação")
    return properties

def verificar_disponibilidade(data: str, horario: str) -> bool:
    """
    Verifica se o horário está disponível no Notion
    """
    if not notion or not NOTION_DATABASE_ID:
        # Modo offline - sempre retorna True para desenvolvimento
        return True
    
    try:
        # Parsear data
        data_obj = datetime.strptime(data, '%Y-%m-%d')
        dia_semana = data_obj.strftime('%A').lower()
        
        # Verificar se é dia útil
        if dia_semana not in HORARIOS_DISPONIVEIS:
            return False
        
        # Verificar se horário está na lista
        if horario not in HORARIOS_DISPONIVEIS[dia_semana]:
            return False
        
        # Consultar Notion para ver se já está agendado
        filtro = {
            "and": [
                {
                    "property": "Data",
                    "date": {
                        "equals": data
                    }
                },
                {
                    "property": "Horário",
                    "rich_text": {
                        "equals": horario
                    }
                },
                {
                    "property": "Status",
                    "select": {
                        "does_not_equal": "Cancelado"
                    }
                }
            ]
        }
        
        results = notion.databases.query(
            database_id=NOTION_DATABASE_ID,
            filter=filtro
        )
        
        # Se não há resultados, está disponível
        return len(results.get("results", [])) == 0
        
    except Exception as e:
        logger.error(f"Erro ao verificar disponibilidade: {str(e)}")
        return False

def criar_agendamento_notion(agendamento: AgendamentoCreate) -> dict:
    """
    Cria um novo agendamento no Notion
    """
    if not notion or not NOTION_DATABASE_ID:
        # Modo offline - retorna mock
        return {
            "id": "mock-id-12345",
            "created_time": datetime.now().isoformat()
        }
    
    try:
        # Preparar dados para Notion
        properties = {
            "Nome": {
                "title": [
                    {
                        "text": {
                            "content": agendamento.nome
                        }
                    }
                ]
            },
            "Email": {
                "email": agendamento.email
            },
            "Telefone": {
                "phone_number": agendamento.telefone
            },
            "Data": {
                "date": {
                    "start": agendamento.data
                }
            },
            "Horário": {
                "rich_text": [
                    {
                        "text": {
                            "content": agendamento.horario
                        }
                    }
                ]
            },
            "Tipo": {
                "select": {
                    "name": "Online" if agendamento.tipo_atendimento == "online" else "Presencial"
                }
            },
            "Status": {
                "select": {
                    "name": "Pendente"
                }
            },
            "Mensagem": {
                "rich_text": [
                    {
                        "text": {
                            "content": agendamento.mensagem or ""
                        }
                    }
                ]
            }
        }
        
        # Criar página no Notion
        page = notion.pages.create(
            parent={"database_id": NOTION_DATABASE_ID},
            properties=properties
        )
        
        logger.info(f"Agendamento criado: {page['id']}")
        return page
        
    except Exception as e:
        logger.error(f"Erro ao criar agendamento: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao criar agendamento: {str(e)}")

# Rotas da API
@app.get("/")
def root():
    """Endpoint raiz"""
    return {
        "message": "Agenda Wellington CR - API",
        "version": "1.0.0",
        "notion_connected": notion is not None and NOTION_DATABASE_ID != ""
    }

@app.get("/health")
def health_check():
    """Health check"""
    return {
        "status": "healthy",
        "notion_configured": notion is not None
    }

@app.get("/disponibilidade/{data}")
def obter_disponibilidade(data: str) -> DisponibilidadeResponse:
    """
    Retorna slots disponíveis para uma data específica
    """
    try:
        # Validar formato da data
        data_obj = datetime.strptime(data, '%Y-%m-%d')
        
        # Verificar se não é passado
        if data_obj.date() < datetime.now().date():
            raise HTTPException(status_code=400, detail="Data não pode ser no passado")
        
        # Obter dia da semana
        dia_semana = data_obj.strftime('%A').lower()
        
        # Se não é dia útil, retornar vazio
        if dia_semana not in HORARIOS_DISPONIVEIS:
            return DisponibilidadeResponse(data=data, slots=[])
        
        # Verificar disponibilidade de cada horário
        slots = []
        for horario in HORARIOS_DISPONIVEIS[dia_semana]:
            disponivel = verificar_disponibilidade(data, horario)
            slots.append(SlotDisponivel(
                data=data,
                horario=horario,
                disponivel=disponivel
            ))
        
        return DisponibilidadeResponse(data=data, slots=slots)
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato de data inválido. Use YYYY-MM-DD")
    except Exception as e:
        logger.error(f"Erro ao obter disponibilidade: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/agendar")
def criar_agendamento(agendamento: AgendamentoCreate):
    """
    Cria um novo agendamento
    """
    try:
        # Verificar disponibilidade
        if not verificar_disponibilidade(agendamento.data, agendamento.horario):
            raise HTTPException(
                status_code=409, 
                detail="Horário não disponível. Por favor, escolha outro."
            )
        
        # Criar agendamento no Notion
        resultado = criar_agendamento_notion(agendamento)
        
        return {
            "success": True,
            "message": "Agendamento criado com sucesso!",
            "agendamento_id": resultado.get("id", ""),
            "data": agendamento.data,
            "horario": agendamento.horario
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao criar agendamento: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao processar agendamento: {str(e)}")

@app.get("/proximos-dias/{num_dias}")
def obter_proximos_dias_disponiveis(num_dias: int = 30):
    """
    Retorna os próximos dias com disponibilidade
    """
    try:
        dias_disponiveis = []
        data_atual = datetime.now().date()
        
        for i in range(num_dias):
            data = data_atual + timedelta(days=i)
            dia_semana = data.strftime('%A').lower()
            
            # Só incluir dias úteis
            if dia_semana in HORARIOS_DISPONIVEIS:
                dias_disponiveis.append({
                    "data": data.strftime('%Y-%m-%d'),
                    "dia_semana": dia_semana,
                    "data_formatada": data.strftime('%d/%m/%Y')
                })
        
        return {
            "dias": dias_disponiveis
        }
        
    except Exception as e:
        logger.error(f"Erro ao obter próximos dias: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
