#!/usr/bin/env python3
# ════════════════════════════════════════════════════════
# 🐕 HEARTBEAT MEMORY SEARCH - AUTO CHECK
# ════════════════════════════════════════════════════════
# Búsqueda automática en memoria durante heartbeats
# Autor: Perrobotillo 🐕
# ════════════════════════════════════════════════════════

import requests
import json
from pathlib import Path
from datetime import datetime
import sys

WORKSPACE = Path("/home/overgon/.openclaw/workspace")
MEMORY_FILE = WORKSPACE / "MEMORY.md"
MEMORY_DIR = WORKSPACE / "memory"
OLLAMA_URL = "http://localhost:11434/api/embeddings"

def get_embedding(text: str) -> list:
    """Obtener embedding usando Ollama local"""
    try:
        response = requests.post(
            OLLAMA_URL,
            json={"model": "nomic-embed-text", "prompt": text[:500]},
            timeout=10
        )
        if response.status_code == 200:
            return response.json().get('embedding', [])
    except:
        pass
    return []

def cosine_similarity(vec1: list, vec2: list) -> float:
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = sum(a * a for a in vec1) ** 0.5
    norm2 = sum(b * b for b in vec2) ** 0.5
    return dot_product / (norm1 * norm2) if norm1 > 0 and norm2 > 0 else 0.0

def search_memory(query: str, top_k: int = 3) -> list:
    """Buscar en memoria"""
    query_embedding = get_embedding(query)
    if not query_embedding:
        return []
    
    results = []
    
    # Buscar en MEMORY.md
    if MEMORY_FILE.exists():
        with open(MEMORY_FILE, 'r') as f:
            content = f.read()
        chunks = content.split('\n\n')
        for chunk in chunks[:20]:  # Limitar para speed
            if len(chunk.strip()) < 30:
                continue
            chunk_emb = get_embedding(chunk[:500])
            if chunk_emb:
                sim = cosine_similarity(query_embedding, chunk_emb)
                if sim > 0.4:
                    results.append({'source': 'MEMORY.md', 'text': chunk[:150], 'sim': sim})
    
    # Buscar en daily notes recientes
    if MEMORY_DIR.exists():
        for daily_file in sorted(MEMORY_DIR.glob("*.md"), reverse=True)[:5]:
            with open(daily_file, 'r') as f:
                content = f.read()[:800]
            file_emb = get_embedding(content)
            if file_emb:
                sim = cosine_similarity(query_embedding, file_emb)
                if sim > 0.4:
                    results.append({'source': f'memory/{daily_file.name}', 'text': content[:150], 'sim': sim})
    
    results.sort(key=lambda x: x['sim'], reverse=True)
    return results[:top_k]

def check_heartbeats():
    """Check automático para heartbeats - SOLO NOTIFICAR SI HAY PROBLEMAS RECIENTES (<7 días)"""
    from datetime import timedelta
    
    # Calcular fecha límite (7 días atrás)
    hoy = datetime.now()
    fecha_limite = hoy - timedelta(days=7)
    
    queries = [
        ("emergency close|SL cruzado", "🚨 Emergency closes"),
        ("drawdown >5%|pérdida grande", "💔 Drawdowns críticos"),
        ("bug crítico|error fatal|bot cayó", "🐛 Bugs críticos"),
        ("API error|timeout|connection", "⚠️ Errores de API"),
    ]
    
    hallazgos_relevantes = []
    
    for pattern, label in queries:
        results = search_memory(pattern, top_k=3)
        # Solo guardar resultados con similitud ALTA (>0.6) Y recientes (<7 días)
        relevantes = []
        for r in results:
            # Extraer fecha del nombre del archivo (ej: memory/2026-06-04-1340.md)
            es_reciente = True
            if 'memory/' in r['source']:
                try:
                    # Intentar parsear fecha del filename
                    partes = r['source'].replace('memory/', '').replace('.md', '').split('-')
                    if len(partes) >= 3:
                        año, mes, dia = int(partes[0]), int(partes[1]), int(partes[2])
                        fecha_doc = datetime(año, mes, dia)
                        es_reciente = fecha_doc >= fecha_limite
                except:
                    pass  # Si no puede parsear, asume que es reciente
            
            if r['sim'] > 0.6 and es_reciente:
                relevantes.append(r)
        
        if relevantes:
            hallazgos_relevantes.append((label, relevantes))
    
    # SOLO NOTIFICAR si hay hallazgos relevantes
    if hallazgos_relevantes:
        print("=" * 60)
        print("🚨 HALLAZGOS RELEVANTES DETECTADOS (últimos 7 días)")
        print("=" * 60)
        for label, results in hallazgos_relevantes:
            print(f"\n{label}:")
            for r in results:
                print(f"  [{r['sim']:.2f}] {r['source']}: {r['text'][:100]}...")
        print("\n" + "=" * 60)
        return True  # Hay algo que reportar
    else:
        print("✅ Sin novedades relevantes (últimos 7 días) - No notificar")
        return False  # Todo bien, no notificar

if __name__ == "__main__":
    if len(sys.argv) > 1:
        query = ' '.join(sys.argv[1:])
        results = search_memory(query)
        print(f"\n🔍 Resultados para: '{query}'\n")
        for i, r in enumerate(results, 1):
            print(f"{i}. [{r['sim']:.3f}] {r['source']}")
            print(f"   {r['text'][:120]}...\n")
    else:
        check_heartbeats()
