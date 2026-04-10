from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel, EmailStr, validator
from datetime import datetime, timedelta
from typing import List, Optional, Dict
import os
from notion_client import Client
import logging
from dotenv import load_dotenv
from functools import lru_cache
import asyncio
from concurrent.futures import ThreadPoolExecutor

load_dotenv()

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Inicializar FastAPI
app = FastAPI(
    title="Agenda Wellington CR",
    description="Sistema de agendamento integrado ao Notion (Otimizado)",
    version="2.0.0"
)

# CORS - Permitir requisições do site
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Em produção, especifique o domínio do site
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Compressão GZIP para respostas mais rápidas
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Configuração do Notion
NOTION_TOKEN = os.getenv("NOTION_TOKEN", "")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID", "")

# Inicializar cliente Notion
notion = Client(auth=NOTION_TOKEN) if NOTION_TOKEN else None

# Thread pool para operações assíncronas
executor = ThreadPoolExecutor(max_workers=3)

# Cache em memória (simples)
cache_store: Dict[str, tuple] = {}  # {key: (data, timestamp)}
CACHE_TTL = 10 * 60  # 10 minutos em segundos

# Horários disponíveis (Segunda a Sexta, 14h às 22h)
HORARIOS_DISPONIVEIS = {
    "monday": ["14:00", "15:00", "16:00", "17:00", "18:00", "19:00", "20:00", "21:00"],
    "tuesday": ["14:00", "15:00", "16:00", "17:00", "18:00", "19:00", "20:00", "21:00"],
    "wednesday": ["14:00", "15:00", "16:00", "17:00", "18:00", "19:00", "20:00", "21:00"],
    "thursday": ["14:00", "15:00", "16:00", "17:00", "18:00", "19:00", "20:00", "21:00"],
    "friday": ["14:00", "15:00", "16:00", "17:00", "18:00", "19:00", "20:00", "21:00"],
}

# ===== FUNÇÕES DE CACHE =====

def get_cache(key: str):
    """Recupera item do cache se ainda válido"""
    if key in cache_store:
        data, timestamp = cache_store[key]
        if datetime.now().timestamp() - timestamp < CACHE_TTL:
            return data
        else:
            del cache_store[key]
    return None

def set_cache(key: str, data):
    """Armazena item no cache"""
    cache_store[key] = (data, datetime.now().timestamp())

def clear_cache_pattern(pattern: str):
    """Limpa cache por padrão de chave"""
    keys_to_delete = [k for k in cache_store.keys() if pattern in k]
    for key in keys_to_delete:
        del cache_store[key]

# ===== MODELOS PYDANTIC =====

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

class DiaDisponivel(BaseModel):
    data: str
    dia_semana: str
    data_formatada: str

class ProximosDiasResponse(BaseModel):
    dias: List[DiaDisponivel]

# ===== FUNÇÕES AUXILIARES OTIMIZADAS =====

def verificar_disponibilidade_batch(datas_horarios: List[tuple]) -> Dict[str, bool]:
    """
    Verifica disponibilidade de múltiplos horários de uma vez
    Retorna: {f"{data}_{horario}": bool}
    """
    if not notion or not NOTION_DATABASE_ID:
        return {f"{data}_{horario}": True for data, horario in datas_horarios}
    
    try:
        # Agrupar por data para otimizar consultas
        datas_unicas = list(set(data for data, _ in datas_horarios))
        
        resultados = {}
        
        for data in datas_unicas:
            # Consultar todos os agendamentos do dia de uma vez
            filtro = {
                "and": [
                    {
                        "property": "Data",
                        "date": {"equals": data}
                    },
                    {
                        "property": "Status",
                        "select": {"does_not_equal": "Cancelado"}
                    }
                ]
            }
            
            results = notion.databases.query(
                database_id=NOTION_DATABASE_ID,
                filter=filtro
            )
            
            # Extrair horários ocupados
            horarios_ocupados = set()
            for page in results.get("results", []):
                horario_prop = page.get("properties", {}).get("Horário", {})
                rich_text = horario_prop.get("rich_text", [])
                if rich_text:
                    horario = rich_text[0].get("text", {}).get("content", "")
                    horarios_ocupados.add(horario)
            
            # Marcar disponibilidade para todos os horários dessa data
            for data_check, horario in datas_horarios:
                if data_check == data:
                    key = f"{data}_{horario}"
                    resultados[key] = horario not in horarios_ocupados
        
        return resultados
        
    except Exception as e:
        logger.error(f"Erro ao verificar disponibilidade batch: {str(e)}")
        return {f"{data}_{horario}": False for data, horario in datas_horarios}

def verificar_disponibilidade(data: str, horario: str) -> bool:
    """Versão com cache da verificação de disponibilidade"""
    
    # Verificar cache primeiro
    cache_key = f"disponivel_{data}_{horario}"
    cached = get_cache(cache_key)
    if cached is not None:
        return cached
    
    if not notion or not NOTION_DATABASE_ID:
        return True
    
    try:
        data_obj = datetime.strptime(data, '%Y-%m-%d')
        dia_semana = data_obj.strftime('%A').lower()
        
        if dia_semana not in HORARIOS_DISPONIVEIS:
            set_cache(cache_key, False)
            return False
        
        if horario not in HORARIOS_DISPONIVEIS[dia_semana]:
            set_cache(cache_key, False)
            return False
        
        filtro = {
            "and": [
                {"property": "Data", "date": {"equals": data}},
                {"property": "Horário", "rich_text": {"equals": horario}},
                {"property": "Status", "select": {"does_not_equal": "Cancelado"}}
            ]
        }
        
        results = notion.databases.query(
            database_id=NOTION_DATABASE_ID,
            filter=filtro
        )
        
        disponivel = len(results.get("results", [])) == 0
        set_cache(cache_key, disponivel)
        return disponivel
        
    except Exception as e:
        logger.error(f"Erro ao verificar disponibilidade: {str(e)}")
        return False

def criar_agendamento_notion(agendamento: AgendamentoCreate) -> dict:
    """Cria agendamento e limpa cache relacionado"""
    if not notion or not NOTION_DATABASE_ID:
        return {
            "id": "mock-id-12345",
            "created_time": datetime.now().isoformat()
        }
    
    try:
        properties = {
            "Nome": {
                "title": [{"text": {"content": agendamento.nome}}]
            },
            "Email": {"email": agendamento.email},
            "Telefone": {"phone_number": agendamento.telefone},
            "Data": {"date": {"start": agendamento.data}},
            "Horário": {
                "rich_text": [{"text": {"content": agendamento.horario}}]
            },
            "Tipo": {
                "select": {
                    "name": "Online" if agendamento.tipo_atendimento == "online" else "Presencial"
                }
            },
            "Status": {"select": {"name": "Pendente"}},
            "Mensagem": {
                "rich_text": [{"text": {"content": agendamento.mensagem or ""}}]
            }
        }
        
        page = notion.pages.create(
            parent={"database_id": NOTION_DATABASE_ID},
            properties=properties
        )
        
        # Limpar cache da data agendada
        clear_cache_pattern(agendamento.data)
        
        logger.info(f"Agendamento criado: {page['id']}")
        return page
        
    except Exception as e:
        logger.error(f"Erro ao criar agendamento: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao criar agendamento: {str(e)}")

# ===== ROTAS DA API =====

@app.get("/")
def root():
    """Endpoint raiz"""
    return {
        "message": "Agenda Wellington CR - API Otimizada",
        "version": "2.0.0",
        "notion_connected": notion is not None and NOTION_DATABASE_ID != "",
        "features": ["cache", "gzip", "batch-queries", "auto-scroll"]
    }

@app.get("/health")
def health_check():
    """Health check"""
    return {
        "status": "healthy",
        "notion_configured": notion is not None,
        "cache_entries": len(cache_store)
    }

@app.get("/disponibilidade/{data}", response_model=DisponibilidadeResponse)
async def obter_disponibilidade(data: str):
    """Retorna slots disponíveis (com cache)"""
    
    # Verificar cache
    cache_key = f"slots_{data}"
    cached = get_cache(cache_key)
    if cached:
        return cached
    
    try:
        data_obj = datetime.strptime(data, '%Y-%m-%d')
        
        if data_obj.date() < datetime.now().date():
            raise HTTPException(status_code=400, detail="Data não pode ser no passado")
        
        dia_semana = data_obj.strftime('%A').lower()
        
        if dia_semana not in HORARIOS_DISPONIVEIS:
            response = DisponibilidadeResponse(data=data, slots=[])
            set_cache(cache_key, response)
            return response
        
        # Preparar lista de verificações
        horarios = HORARIOS_DISPONIVEIS[dia_semana]
        datas_horarios = [(data, h) for h in horarios]
        
        # Verificação em batch
        disponibilidades = verificar_disponibilidade_batch(datas_horarios)
        
        slots = [
            SlotDisponivel(
                data=data,
                horario=horario,
                disponivel=disponibilidades.get(f"{data}_{horario}", False)
            )
            for horario in horarios
        ]
        
        response = DisponibilidadeResponse(data=data, slots=slots)
        set_cache(cache_key, response)
        return response
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato de data inválido. Use YYYY-MM-DD")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao obter disponibilidade: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/agendar")
async def criar_agendamento(agendamento: AgendamentoCreate):
    """Cria um novo agendamento"""
    try:
        if not verificar_disponibilidade(agendamento.data, agendamento.horario):
            raise HTTPException(
                status_code=409, 
                detail="Horário não disponível. Por favor, escolha outro."
            )
        
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

@app.get("/proximos-dias/{num_dias}", response_model=ProximosDiasResponse)
async def obter_proximos_dias_disponiveis(num_dias: int = 30):
    """Retorna próximos dias com disponibilidade (com cache)"""
    
    # Verificar cache
    cache_key = f"proximos_dias_{num_dias}"
    cached = get_cache(cache_key)
    if cached:
        return cached
    
    try:
        dias_disponiveis = []
        data_atual = datetime.now().date()
        
        for i in range(num_dias):
            data = data_atual + timedelta(days=i)
            dia_semana = data.strftime('%A').lower()
            
            if dia_semana in HORARIOS_DISPONIVEIS:
                dias_disponiveis.append(
                    DiaDisponivel(
                        data=data.strftime('%Y-%m-%d'),
                        dia_semana=dia_semana,
                        data_formatada=data.strftime('%d/%m/%Y')
                    )
                )
        
        response = ProximosDiasResponse(dias=dias_disponiveis)
        set_cache(cache_key, response)
        return response
        
    except Exception as e:
        logger.error(f"Erro ao obter próximos dias: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/cache")
async def limpar_cache():
    """Endpoint para limpar cache (útil para testes)"""
    cache_store.clear()
    return {"message": "Cache limpo com sucesso", "status": "ok"}

# ===== LIMPEZA AUTOMÁTICA DE CACHE =====

@app.on_event("startup")
async def startup_event():
    """Inicialização do app"""
    logger.info("🚀 Agenda Wellington CR - API Otimizada iniciada")
    logger.info(f"Notion conectado: {notion is not None}")
    logger.info(f"Database ID configurado: {NOTION_DATABASE_ID != ''}")

# Limpar cache expirado periodicamente
import asyncio
from fastapi import BackgroundTasks

async def cleanup_expired_cache():
    """Remove entradas expiradas do cache"""
    while True:
        await asyncio.sleep(300)  # A cada 5 minutos
        now = datetime.now().timestamp()
        expired_keys = [
            k for k, (_, ts) in cache_store.items() 
            if now - ts > CACHE_TTL
        ]
        for key in expired_keys:
            del cache_store[key]
        if expired_keys:
            logger.info(f"🧹 Removidas {len(expired_keys)} entradas expiradas do cache")

@app.on_event("startup")
async def start_cache_cleanup():
    asyncio.create_task(cleanup_expired_cache())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
