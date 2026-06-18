#!/usr/bin/env python3
# ════════════════════════════════════════════════════════
# 🐕 MEMORY SEARCH LOCAL - OLLAMA EMBEDDINGS
# ════════════════════════════════════════════════════════
# Búsqueda semántica local usando Ollama + nomic-embed-text
# Autor: Perrobotillo 🐕
# ════════════════════════════════════════════════════════

import requests
import json
from pathlib import Path
from datetime import datetime

WORKSPACE = Path("/home/overgon/.openclaw/workspace")
MEMORY_DIR = WORKSPACE / "memory"
MEMORY_FILE = WORKSPACE / "MEMORY.md"
OLLAMA_URL = "http://localhost:11434/api/embeddings"

def get_embedding(text: str) -> list:
    """Obtener embedding de texto usando Ollama local"""
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": "nomic-embed-text",
                "prompt": text
            },
            timeout=10
        )
        
        if response.status_code == 200:
            return response.json().get('embedding', [])
        else:
            print(f"❌ Error Ollama: {response.status_code}")
            return []
    except Exception as e:
        print(f"❌ Error conexión: {e}")
        return []

def cosine_similarity(vec1: list, vec2: list) -> float:
    """Calcular similitud coseno entre dos vectores"""
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0
    
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = sum(a * a for a in vec1) ** 0.5
    norm2 = sum(b * b for b in vec2) ** 0.5
    
    if norm1 == 0 or norm2 == 0:
        return 0.0
    
    return dot_product / (norm1 * norm2)

def search_memory(query: str, top_k: int = 5) -> list:
    """Buscar en memoria usando embeddings"""
    
    print(f"🔍 Buscando: '{query}'")
    
    # Obtener embedding del query
    query_embedding = get_embedding(query)
    if not query_embedding:
        print("❌ No se pudo generar embedding")
        return []
    
    results = []
    
    # Buscar en MEMORY.md
    if MEMORY_FILE.exists():
        with open(MEMORY_FILE, 'r') as f:
            content = f.read()
        
        # Dividir en secciones (por líneas vacías o headers)
        chunks = content.split('\n\n')
        
        for i, chunk in enumerate(chunks):
            if len(chunk.strip()) < 20:  # Skip chunks muy cortos
                continue
            
            chunk_embedding = get_embedding(chunk[:500])  # Limitar longitud
            if chunk_embedding:
                similarity = cosine_similarity(query_embedding, chunk_embedding)
                
                if similarity > 0.3:  # Threshold mínimo
                    results.append({
                        'source': 'MEMORY.md',
                        'chunk': chunk[:200] + '...' if len(chunk) > 200 else chunk,
                        'similarity': similarity,
                        'position': i
                    })
    
    # Buscar en memory/*.md (daily notes)
    if MEMORY_DIR.exists():
        for daily_file in sorted(MEMORY_DIR.glob("*.md"), reverse=True)[:10]:
            with open(daily_file, 'r') as f:
                content = f.read()
            
            # Tomar primeros 1000 chars para speed
            file_embedding = get_embedding(content[:1000])
            if file_embedding:
                similarity = cosine_similarity(query_embedding, file_embedding)
                
                if similarity > 0.3:
                    results.append({
                        'source': f'memory/{daily_file.name}',
                        'chunk': content[:200] + '...',
                        'similarity': similarity,
                        'position': 0
                    })
    
    # Ordenar por similitud
    results.sort(key=lambda x: x['similarity'], reverse=True)
    
    return results[:top_k]

def main():
    """Test interactivo"""
    import sys
    
    if len(sys.argv) > 1:
        query = ' '.join(sys.argv[1:])
    else:
        query = "¿Cuándo cerramos SOL por emergencia?"
    
    print("=" * 60)
    print("🐕 MEMORY SEARCH LOCAL - OLLAMA")
    print("=" * 60)
    print()
    
    results = search_memory(query, top_k=5)
    
    if results:
        print(f"\n✅ {len(results)} resultados encontrados:\n")
        for i, result in enumerate(results, 1):
            print(f"{i}. [{result['similarity']:.3f}] {result['source']}")
            print(f"   {result['chunk'][:100]}...")
            print()
    else:
        print("\n⚠️ No se encontraron resultados relevantes")
    
    print("=" * 60)

if __name__ == "__main__":
    main()
