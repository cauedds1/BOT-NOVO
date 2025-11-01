import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json

from api_client import buscar_jogos_do_dia
from analysts.master_analyzer import generate_match_analysis
from db_manager import DatabaseManager

logger = logging.getLogger(__name__)

MAX_QUEUE_SIZE = 1000
analysis_queue = asyncio.Queue(maxsize=MAX_QUEUE_SIZE)

job_status = {}

class AnalysisJob:
    def __init__(self, user_id: int, analysis_type: str, league_id: Optional[int] = None, fixture_id: Optional[int] = None):
        self.user_id = user_id
        self.analysis_type = analysis_type
        self.league_id = league_id
        self.fixture_id = fixture_id
        self.job_id = f"{user_id}_{analysis_type}_{datetime.now().timestamp()}"
        self.status = "queued"
        self.total_fixtures = 0
        self.processed = 0
        self.created_at = datetime.now()
        self.completed_at = None

async def add_analysis_job(user_id: int, analysis_type: str, league_id: Optional[int] = None, fixture_id: Optional[int] = None):
    """
    Adiciona um job de análise à fila com proteção contra sobrecarga.
    
    Returns:
        str: job_id se adicionado com sucesso
        None: se a fila estiver cheia
    """
    if analysis_queue.qsize() >= MAX_QUEUE_SIZE:
        logger.warning(f"⚠️ Fila de análises CHEIA ({MAX_QUEUE_SIZE}/{MAX_QUEUE_SIZE}). Job rejeitado para user {user_id}")
        return None
    
    job = AnalysisJob(user_id, analysis_type, league_id, fixture_id)
    job_status[job.job_id] = job
    
    try:
        await asyncio.wait_for(analysis_queue.put(job), timeout=1.0)
        logger.info(f"✅ Job {job.job_id} adicionado à fila ({analysis_queue.qsize()}/{MAX_QUEUE_SIZE}). Tipo: {analysis_type}")
        return job.job_id
    except asyncio.TimeoutError:
        logger.error(f"❌ Timeout ao adicionar job à fila. Fila pode estar bloqueada.")
        del job_status[job.job_id]
        return None

def get_job_status(job_id: str) -> Optional[Dict]:
    job = job_status.get(job_id)
    if job:
        return {
            "job_id": job.job_id,
            "status": job.status,
            "progress": f"{job.processed}/{job.total_fixtures}",
            "type": job.analysis_type
        }
    return None

def get_queue_stats() -> Dict:
    """
    Retorna estatísticas da fila de análises.
    
    Returns:
        Dict com: queue_size, max_size, utilization_percent
    """
    current_size = analysis_queue.qsize()
    return {
        "queue_size": current_size,
        "max_size": MAX_QUEUE_SIZE,
        "utilization_percent": round((current_size / MAX_QUEUE_SIZE) * 100, 1),
        "is_full": current_size >= MAX_QUEUE_SIZE
    }

def cleanup_old_jobs(max_age_hours: int = 24):
    """
    Remove jobs completados ou falhados com mais de X horas.
    Previne memory leak mantendo apenas jobs recentes.
    
    Args:
        max_age_hours: Idade máxima em horas (padrão: 24h)
    """
    now = datetime.now()
    cutoff_time = now - timedelta(hours=max_age_hours)
    
    jobs_to_remove = []
    for job_id, job in job_status.items():
        # Remover se for job completado/falhado antigo
        if job.status in ["completed", "failed"]:
            if job.completed_at and job.completed_at < cutoff_time:
                jobs_to_remove.append(job_id)
            # Se não tem completed_at mas foi criado há muito tempo, remover também
            elif not job.completed_at and job.created_at < cutoff_time:
                jobs_to_remove.append(job_id)
    
    for job_id in jobs_to_remove:
        del job_status[job_id]
    
    if jobs_to_remove:
        logger.info(f"🧹 Limpeza automática: {len(jobs_to_remove)} jobs antigos removidos")
    
    return len(jobs_to_remove)

async def background_analysis_worker(db_manager: DatabaseManager):
    logger.info("🚀 Background analysis worker iniciado!")
    
    while True:
        try:
            job = await analysis_queue.get()
            logger.info(f"📋 Processando job {job.job_id} - Tipo: {job.analysis_type}")
            
            job.status = "processing"
            
            fixtures_to_analyze = []
            if job.fixture_id:
                fixtures_to_analyze = [{"fixture": {"id": job.fixture_id}}]
            elif job.league_id:
                from api_client import buscar_jogos_por_liga
                fixtures_to_analyze = await buscar_jogos_por_liga(job.league_id) or []
            else:
                fixtures_to_analyze = await buscar_jogos_do_dia() or []
            
            job.total_fixtures = len(fixtures_to_analyze)
            logger.info(f"📊 {job.total_fixtures} jogos para analisar")
            
            for jogo in fixtures_to_analyze:
                try:
                    fixture_id = jogo.get('fixture', {}).get('id')
                    if not fixture_id:
                        continue
                    
                    logger.info(f"🔍 Analisando fixture {fixture_id}...")
                    
                    analysis_packet = await generate_match_analysis(jogo)
                    
                    dossier_json = json.dumps(analysis_packet, ensure_ascii=False)
                    
                    await asyncio.to_thread(
                        db_manager.save_daily_analysis,
                        fixture_id=fixture_id,
                        analysis_type=job.analysis_type,
                        dossier_json=dossier_json,
                        user_id=job.user_id
                    )
                    
                    job.processed += 1
                    logger.info(f"✅ Fixture {fixture_id} analisado ({job.processed}/{job.total_fixtures})")
                    
                except Exception as e:
                    logger.error(f"❌ Erro ao analisar fixture: {e}")
                    continue
                
                await asyncio.sleep(0.1)
            
            job.status = "completed"
            job.completed_at = datetime.now()
            logger.info(f"🎉 Job {job.job_id} concluído! {job.processed} jogos analisados")
            
            # Limpeza automática a cada job completado
            cleanup_old_jobs()
            
            analysis_queue.task_done()
            
        except Exception as e:
            logger.error(f"❌ Erro no background worker: {e}")
            if 'job' in locals():
                job.status = "failed"
                job.completed_at = datetime.now()
            await asyncio.sleep(1)
